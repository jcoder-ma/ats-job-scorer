"""Explainable personal job-fit scoring. No external AI or network calls."""
import base64
import hashlib
import html
import io
import json
import math
import re
import zipfile
from xml.etree import ElementTree as ET

VERSION = '1.0.0'
MAX_TEXT = 150000
MAX_FILE = 8 * 1024 * 1024
CATEGORIES = {
 'Leadership': 20, 'Architecture and technical skills': 20,
 'Delivery and collaboration': 15, 'Reliability and security': 20,
 'AI and developer productivity': 15, 'Business and domain': 10,
}
# Exact aliases only. Related but different technologies are deliberately separate.
GROUPS = {
 'Leadership': {
  'People management':['people management','direct reports','managed a team','managing teams','engineering manager','led a team','led teams'],
  'Managing managers':['managing managers','managed managers','engineering managers','second-line'],
  'Hiring':['hiring','recruiting','recruit','hired'], 'Coaching':['coaching','mentoring','mentored','career development','career growth'],
  'Organization design':['succession planning','organizational design','organization design','talent strategy'],
 },
 'Architecture and technical skills': {
  'Python':['python'], 'FastAPI':['fastapi'], 'Java':['java'], 'JavaScript':['javascript'], 'TypeScript':['typescript'],
  'React':['react','react.js'], 'Node.js':['node.js','nodejs'], 'Go':['golang','go'], 'C#':['c#','csharp'], '.NET':['.net','dotnet'],
  'SQL Server':['sql server','mssql'], 'PostgreSQL':['postgresql','postgres'], 'SQL':['sql'], 'NoSQL':['nosql','cosmos db','mongodb'],
  'AWS':['aws','amazon web services'], 'Azure':['azure'], 'GCP':['gcp','google cloud'],
  'Kubernetes':['kubernetes','k8s'], 'Docker':['docker'], 'Terraform':['terraform'], 'Helm':['helm'],
  'GitOps':['gitops','fleet gitops'], 'Service mesh':['service mesh','istio','linkerd'],
  'Microservices':['microservices','microservice'], 'APIs':['apis','api','restful','rest'],
  'Event-driven systems':['event-driven','event based','event-based','messaging','asynchronous'],
  'Enterprise architecture':['enterprise architecture','reference architecture','reference architectures'],
  'Monolith modernization':['monolith','monolithic','legacy modernization'],
  'Schema decoupling':['schema decoupling','schema separation','shared database','shared schemas','crm-owned','compensation-owned'],
  'Multi-tenant SaaS':['multi-tenant','multitenant','multi tenant'], 'Data pipelines':['etl','data pipeline','data pipelines'],
  'Integrations':['integrations','integration','middleware','mulesoft'],
 },
 'Delivery and collaboration': {
  'Roadmaps':['roadmap','roadmaps'], 'Product partnership':['product management','product managers','product leaders','product leadership'],
  'Agile delivery':['agile','scrum','sprint','sprints'], 'CI/CD':['ci/cd','continuous integration','continuous delivery'],
  'Testing':['automated testing','unit testing','test automation','automated tests'],
  'Vendor management':['vendor management','vendor relationships','vendor accountability'],
  'User discovery':['user feedback','user research','usability','user needs','customer workflows'],
  'Executive communication':['executive leadership','executive communication','stakeholder management'],
 },
 'Reliability and security': {
  'Reliability':['reliability','resiliency','resilience','high availability','high-availability','fault-tolerant','fault tolerance'],
  'Observability':['observability','monitoring','datadog'], 'Incident response':['incident response','incident management','major-incident','on-call'],
  'Disaster recovery':['disaster recovery','disaster-recovery','recovery testing','business continuity'],
  'Zero-downtime deployments':['zero-downtime deployments','zero downtime deployments'],
  'Zero-downtime database migrations':['zero-downtime database','zero downtime database'],
  'Identity and access':['identity','authentication','authorization','iam'], 'OAuth2':['oauth','oauth2','oauth 2.0'],
  'OIDC':['oidc','openid connect'], 'SCIM':['scim'], 'Application security':['application security','appsec','secure sdlc','secure coding','security scanning'],
  'Threat modeling':['threat modeling','threat modelling'], 'Privacy':['privacy','data protection'],
 },
 'AI and developer productivity': {
  'AI-assisted SDLC':['ai-assisted','ai assisted','ai-driven development','ai-native sdlc','codex','copilot'],
  'LLM products':['llm','llms','openai','generative ai','genai','claude'], 'RAG':['rag','retrieval-augmented','retrieval augmented'],
  'Tool calling':['tool calling','function calling'], 'AI platform SDKs':['llm sdk','ai sdk','internal sdk'],
  'Internal developer tools':['developer enablement','developer platform','developer tooling','internal tools','internal tooling'],
  'AI governance':['ai governance','prompt injection','bias auditing'], 'PyTorch':['pytorch'], 'LangGraph':['langgraph'],
 },
 'Business and domain': {
  'Financial services':['financial services','fintech','financial-services','banking','wealth management'],
  'Payments':['payments','payment','eft','credit card'], 'Retail merchandising':['merchandising','assortment','space planning','promotions'],
  'SAP':['sap'], 'Blue Yonder':['blue yonder'], 'Telematics':['telematics','mqtt','connected vehicle'],
  'Enterprise SaaS':['enterprise saas','b2b','enterprise applications'], 'Risk management':['risk management','grc'],
 },
}
CONCEPTS = {key: (category, aliases) for category, group in GROUPS.items() for key, aliases in group.items()}
ACTION = re.compile(r'\b(led|built|designed|implemented|delivered|managed|developed|introduced|guided|created|architected|established|migrated|coached|mentored|owned)\b', re.I)
NEGATIVE = re.compile(r'\b(no experience|not experienced|unfamiliar|never used|want to learn|learning goal|target requirement|not evidenced|no direct experience)\b', re.I)
GATE = re.compile(r'\b(work authori[sz]ation|authorized to work|sponsorship|clearance|citizenship|citizen|must reside|must be located|in.office|onsite|on.site|travel|relocat|seed|series [ab])', re.I)
YEAR = re.compile(r'(\d+)\s*\+?\s*years?', re.I)
PREFERRED = re.compile(r'preferred|nice to have|strong plus|bonus qualifications|great if|strong candidates may', re.I)
HEADING = re.compile(r'^(?:minimum |basic |required )?qualifications|^requirements|^what you.ll (?:do|bring)|^responsibilities|^you may be', re.I)


def clean(value):
    if not isinstance(value, str):
        raise ValueError('Text must be a string.')
    if len(value) > MAX_TEXT:
        raise ValueError('Text is too long; use fewer than 150,000 characters.')
    return html.unescape(value).replace('\u00a0', ' ').strip()


def has(text, alias):
    return bool(re.search(r'(?<![\w])' + re.escape(alias) + r'(?![\w])', text, re.I))


def concepts(text):
    found = {key for key, (_, aliases) in CONCEPTS.items() if any(has(text, a) for a in aliases)}
    # Do not mistake English "go" for a language unless technical context supports it.
    if 'Go' in found and not re.search(r'golang|python|java|typescript|languages?|\bgo\s+(developer|engineer|programming)', text, re.I):
        found.remove('Go')
    return found


def lines(text):
    return [re.sub(r'^\s*(?:[-*•▪]|\d+[.)])\s*', '', x).strip() for x in re.split(r'[\r\n]+', clean(text)) if x.strip()]


def extract_requirements(job):
    """Rule-based draft, always editable; retains unrecognized requirements."""
    rows, seen = [], set()
    importance = 'core'
    def add(text, concept, category, kind):
        identity = concept if concept else (text.lower(), kind)
        if identity in seen and concept and kind == 'core':
            prior = next((r for r in rows if r['concept'] == concept), None)
            if prior and prior['importance'] == 'preferred':
                prior.update(text=text, category=category, importance=kind)
        if identity in seen:
            return
        seen.add(identity)
        rows.append({'id': f'r{len(rows)+1}', 'text':text, 'concept':concept, 'category':category,
                     'importance':kind, 'reviewed':False, 'level':None, 'reason':'', 'gate_status':'unknown'})
    for raw in lines(job):
        if PREFERRED.search(raw) and len(raw) < 100:
            importance = 'preferred'
            if ':' not in raw:
                continue
        elif HEADING.search(raw) and len(raw) < 80:
            importance = 'core'
            continue
        if len(raw) < 15 or raw.endswith(':'):
            continue
        # Ignore obvious benefit / company marketing paragraphs.
        if re.search(r'\b(401\(?k|paid holidays|dental|vision coverage|salary range|equal opportunity|benefits include)\b', raw, re.I):
            continue
        # Longer prose is broken up for review rather than dropped.
        parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', raw) if len(raw) > 450 else [raw]
        for text in parts:
            if GATE.search(text):
                add(text, '', 'Eligibility', 'eligibility')
                continue
            if YEAR.search(text) or re.search(r"bachelor|master.s degree|degree in", text, re.I):
                add(text, '', 'Eligibility', 'eligibility' if importance == 'core' else 'preferred')
                if importance == 'core':
                    continue
            found = concepts(text)
            for concept in sorted(found):
                add(text, concept, CONCEPTS[concept][0], importance)
            if not found and not YEAR.search(text) and not re.search(r"bachelor|master.s degree|degree in", text, re.I):
                add(text, '', 'Delivery and collaboration', importance)
    if len(rows) > 180:
        raise ValueError('Too many requirements. Paste only the role responsibilities and qualifications.')
    return rows


def evidence_units(resume, experiences=''):
    result=[]
    for source, text in [('Resume',resume), ('Additional experience',experiences)]:
        for i, paragraph in enumerate(lines(text)):
            result.append({'id': f'{source}:{i+1}', 'source':source, 'text':paragraph,
                           'concepts':concepts(paragraph), 'negative':bool(NEGATIVE.search(paragraph))})
    return result


def match_requirement(row, units):
    key=row.get('concept','')
    if not key:
        return {'level':0, 'status':'Not evidenced', 'evidence':[], 'reason':'No automatic concept mapping. Review this requirement and select supporting evidence.'}
    hits=[u for u in units if key in u['concepts']]
    positives=[u for u in hits if not u['negative']]
    negatives=[u for u in hits if u['negative']]
    if negatives and positives:
        return {'level':0, 'status':'Conflicting', 'evidence':(positives+negatives)[:4], 'reason':'Positive and negative statements conflict. Resolve before awarding credit.'}
    if not positives:
        return {'level':0, 'status':'Not evidenced', 'evidence':negatives[:2], 'reason':'No positive supporting statement found. This does not prove the experience is absent.'}
    positives.sort(key=lambda u: bool(ACTION.search(u['text'])) and len(u['text'].split()) >= 10, reverse=True)
    examples=[u for u in positives if ACTION.search(u['text']) and len(u['text'].split()) >= 10]
    level=.75 if examples else .25
    return {'level':level, 'status':'Substantial evidence' if examples else 'Keyword only', 'evidence':positives[:3],
            'reason':'Action-based example found; verify scope and outcomes against the full requirement.' if examples else 'Only an assertion or skill mention was found; add a concrete example.'}


def score(job, resume, experiences='', requirements=None, metadata=None):
    job, resume, experiences=clean(job),clean(resume),clean(experiences)
    if len(job)<40 or len(resume)<40:
        raise ValueError('Add a job description and a resume of at least 40 characters each.')
    rows = extract_requirements(job) if requirements is None else requirements
    if not isinstance(rows,list) or len(rows)>180:
        raise ValueError('Requirements must be a list of at most 180 rows.')
    if not rows:
        raise ValueError('No requirements remain. Add at least one scored requirement.')
    units=evidence_units(resume, experiences)
    scored=[]; gates=[]; ids=set()
    for row in rows:
        if not isinstance(row,dict) or not row.get('id') or row['id'] in ids:
            raise ValueError('Each requirement needs a unique ID.')
        ids.add(row['id'])
        if row.get('importance') not in ('core','preferred','eligibility'):
            raise ValueError('Invalid requirement importance.')
        if not str(row.get('text','')).strip():
            raise ValueError('Requirement text cannot be blank.')
        if row['importance']=='eligibility':
            status=row.get('gate_status','unknown')
            if status not in ('met','unmet','unknown'):
                raise ValueError('Invalid eligibility status.')
            gates.append({'id':row['id'],'text':row['text'],'status':status,'reason':row.get('reason','')})
            continue
        category='Preferred qualifications' if row['importance']=='preferred' else row.get('category')
        if category not in CATEGORIES and category!='Preferred qualifications':
            category='Delivery and collaboration'
        match=match_requirement(row,units)
        reviewed=bool(row.get('reviewed',False))
        level=match['level']
        if reviewed:
            level=row.get('level')
            if isinstance(level,bool) or level not in (0,.25,.5,.75,1):
                raise ValueError('Reviewed scores must be 0, 0.25, 0.5, 0.75 or 1.')
            if not str(row.get('reason','')).strip():
                raise ValueError('Add a rationale for each reviewed score.')
            match['status']={0:'Not evidenced',.25:'Keyword only',.5:'Partial',.75:'Substantial evidence',1:'Demonstrated'}[level]
        scored.append({**row,**match,'level':level,'category':category,'reviewed':reviewed,
                       'reason':row.get('reason') if reviewed else match['reason']})
    if not scored:
        raise ValueError('Add at least one core or preferred requirement; eligibility alone is not a fit score.')
    cats=sorted({r['category'] for r in scored if r['category']!='Preferred qualifications'})
    has_preferred=any(r['category']=='Preferred qualifications' for r in scored)
    if not cats:
        raise ValueError('Add at least one core requirement before scoring.')
    pool=85 if has_preferred else 100
    denominator=sum(CATEGORIES[c] for c in cats)
    raw={c:pool*CATEGORIES[c]/denominator for c in cats}
    weights={c:math.floor(w) for c,w in raw.items()}
    for c in sorted(cats,key=lambda c:raw[c]-weights[c],reverse=True)[:pool-sum(weights.values())]:weights[c]+=1
    if has_preferred:weights['Preferred qualifications']=15
    summary=[]
    for cat,weight in weights.items():
        members=[r for r in scored if r['category']==cat]
        earned=round(weight*sum(r['level'] for r in members)/len(members),2)
        summary.append({'category':cat,'weight':weight,'earned':earned,'count':len(members)})
    total=round(sum(r['earned'] for r in summary),2)
    reviewed=sum(r['reviewed'] for r in scored)
    unknown=sum(g['status']=='unknown' for g in gates)
    unmet=any(g['status']=='unmet' for g in gates)
    recommendation='Apply' if total>=80 else 'Apply as a stretch' if total>=65 else 'Lower priority'
    if unmet:recommendation='Do not apply under the stated conditions'
    confidence='Low' if reviewed<len(scored)*.5 else 'Moderate' if reviewed<len(scored) or unknown else 'High review completeness'
    # Sets are not serialized; supporting excerpts remain exact source text.
    for row in scored:
        row['evidence']=[{k:v for k,v in e.items() if k not in ('concepts','negative')} for e in row['evidence']]
    return {'version':VERSION,'score':total,'rounded_score':int(total+.5),'recommendation':recommendation,
            'confidence':confidence,'reviewed_count':reviewed,'requirement_count':len(scored),'unknown_gates':unknown,
            'categories':summary,'requirements':scored,'eligibility':gates,'metadata':metadata or {},
            'sources':{'resume_sha256':hashlib.sha256(resume.encode()).hexdigest(),'experience_sha256':hashlib.sha256(experiences.encode()).hexdigest()},
            'methodology':'Deterministic, editable evidence rubric. Automatic matches are provisional and capped at 75%. A keyword mention earns 25%. Preferred qualifications total at most 15 points. Eligibility is separate. This is not an employer ATS result, hiring decision, or interview probability. Unrecognized text needs manual review; extraction may miss scope, chronology, alternatives, and negation.'}


def extract_document(name, content):
    data=base64.b64decode(content,validate=True)
    if len(data)>MAX_FILE:raise ValueError('File exceeds the 8 MB limit.')
    suffix=name.lower().rsplit('.',1)[-1]
    if suffix in ('txt','md'):
        result=data.decode('utf-8-sig')
    elif suffix=='docx':
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(x.file_size for x in archive.infolist())>25*1024*1024:raise ValueError('Expanded document is too large.')
            xml=archive.read('word/document.xml')
            root=ET.fromstring(xml)
            ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            result='\n'.join(''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in root.findall('.//w:p',ns))
    elif suffix=='pdf':
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(data))
        if reader.is_encrypted:raise ValueError('Encrypted PDFs are not supported. Upload an unlocked copy or paste text.')
        if len(reader.pages)>30:raise ValueError('Use a PDF of 30 pages or fewer.')
        result='\n'.join(page.extract_text() or '' for page in reader.pages)
    else:raise ValueError('Use PDF, DOCX, TXT or Markdown.')
    if len(result.strip())<40:raise ValueError('Not enough text could be extracted. For scanned files, paste OCR text instead.')
    return clean(result)


def api(payload):
    data=json.loads(payload)
    action=data.pop('action','score')
    if action=='extract':return json.dumps({'text':extract_document(data['name'],data['content'])})
    if action=='requirements':return json.dumps(extract_requirements(data['job']))
    if action=='score':return json.dumps(score(**data))
    raise ValueError('Unknown action.')
