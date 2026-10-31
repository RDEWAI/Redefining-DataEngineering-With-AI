import sys
P="#7A4FB0"; PF="#EEE6F7"; PB="#F7F2FB"; K="#333333"
out=[]
def esc(t): return t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def text(x,y,lines,anchor="middle",size=17,color=K):
    # lines: list of (str, style) style: b,i,n
    dy=size*1.3; y0=y-(len(lines)-1)*dy/2
    for i,(t,s) in enumerate(lines):
        w="bold" if s=="b" else "normal"; st="italic" if s=="i" else "normal"
        out.append(f'<text x="{x}" y="{y0+i*dy}" text-anchor="{anchor}" dominant-baseline="middle" font-family="Arial" font-size="{size if s!="i" else size-2}" font-weight="{w}" font-style="{st}" fill="{color}">{esc(t)}</text>')
def box(x,y,w,h,lines,kind="plain"):
    fill,stroke,sw,da,col="#fff",K,1.6,"",K
    if kind=="ai": fill,stroke,col=PF,P,"#3A1A5A"
    if kind=="person": da='stroke-dasharray="6 4"'
    if kind=="key": sw=3.2
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {da}/>')
    text(x+w/2,y+h/2,lines,color=col)
    return (x,y,w,h)
def cyl(x,y,w,h,lines):
    e=12
    out.append(f'<path d="M{x},{y+e} A{w/2},{e} 0 0 1 {x+w},{y+e} L{x+w},{y+h-e} A{w/2},{e} 0 0 1 {x},{y+h-e} Z" fill="#fff" stroke="{K}" stroke-width="1.6"/>')
    out.append(f'<path d="M{x},{y+e} A{w/2},{e} 0 0 0 {x+w},{y+e}" fill="none" stroke="{K}" stroke-width="1.6"/>')
    text(x+w/2,y+h/2+6,lines); return (x,y,w,h)
def group(x,y,w,h,title,ai=False):
    c=P if ai else K; f=PB if ai else "#fff"
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{f}" stroke="{c}" stroke-width="1.6" stroke-dasharray="7 5"/>')
    out.append(f'<text x="{x+16}" y="{y+26}" font-family="Arial" font-size="18" font-weight="bold" fill="{c if ai else K}">{esc(title)}</text>')
def arrow(pts,ai=False,dash=False,label=None,lpos=None,lcol=None):
    c=P if ai else K; m="ap" if ai else "ak"
    d="M"+" L".join(f"{a},{b}" for a,b in pts)
    da='stroke-dasharray="6 4"' if dash else ""
    out.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{2 if ai else 1.6}" {da} marker-end="url(#{m})"/>')
    if label:
        lx,ly=lpos; lines=label if isinstance(label,list) else [label]
        wmax=max(len(t) for t in lines)*8.3+16; h=len(lines)*20+8
        out.append(f'<rect x="{lx-wmax/2}" y="{ly-h/2}" width="{wmax}" height="{h}" fill="#fff" rx="3"/>')
        text(lx,ly,[(t,"i") for t in lines],color=lcol or c,size=17)
def bot(b,dx=0): x,y,w,h=b; return (x+w/2+dx,y+h)
def top(b,dx=0): x,y,w,h=b; return (x+w/2+dx,y)
def rt(b,dy=0): x,y,w,h=b; return (x+w,y+h/2+dy)
def lf(b,dy=0): x,y,w,h=b; return (x,y+h/2+dy)
def start(W,H):
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="#fff"/>')
    out.append(f'<defs><marker id="ak" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{K}"/></marker><marker id="ap" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{P}"/></marker></defs>')


which=sys.argv[1]
W,H=2400,660
start(W,H)
def rca_band(outs):
    group(30,650,2340,240,"Root Cause Analysis",ai=True)
    AG=box(90,730,280,110,[("Investigation Agent","b"),("gathers evidence,","i"),("drafts findings","i")],"ai")
    HU=box(470,730,260,110,[("Human Reviewer","b"),("confirms cause","i"),("and owner","i")])
    arrow([(230,630),(230,730)],ai=True); arrow([rt(AG),lf(HU)])
    group(830,690,1510,180,"Outputs")
    xs=[860,1230,1600,1970]
    for (t,s_,k),x in zip(outs,xs): box(x,740,340,100,[(t,"b"),(s_,"i")],k)
    arrow([rt(HU),(830,785)])
def evid(p,l,ly,lx=None):
    arrow([p,(p[0],560)],ai=True,dash=True,label=l,lpos=(lx or p[0],ly))
if which=="domain":
    out.clear(); start(1650,660)
    group(30,30,1590,380,"Domain Agents")
    A=box(60,140,140,90,[("User","b")],"person")
    S=box(300,140,200,90,[("Application","b"),("agent + skill","i")])
    R=box(590,140,200,90,[("Knowledge Layer","b"),("retrieval index","i")])
    C=cyl(660,285,210,100,[("Catalog","b"),("semantic layer, ontology,","i"),("data contracts","i")])
    M=box(880,140,180,90,[("Model","b"),("writes the query","i")])
    L=cyl(1160,135,180,100,[("Lakehouse","b"),("gold tables","i")])
    X=box(1420,140,180,90,[("Reconciliation","b")])
    arrow([rt(A,-18),lf(S,-18)],label="question",lpos=(250,150)); arrow([lf(S,18),rt(A,18)],label="answer",lpos=(250,218))
    arrow([(180,230),(180,268),(330,268),(330,230)],label="feedback",lpos=(255,268))
    arrow([rt(S),lf(R)]); arrow([(740,285),(740,230)],label="indexed",lpos=(800,258))
    arrow([rt(R),lf(M)],label="context",lpos=(835,165)); arrow([rt(M),(1160,185)],label="SQL",lpos=(1110,165))
    arrow([rt(L),lf(X)])
    arrow([(1250,135),(1250,95),(400,95),(400,140)],label="rows returned to the application",lpos=(825,95))
    ES=box(60,560,1540,70,[("Trace and Evidence Store","b"),("OpenTelemetry spans, logs, eval results","i")],"ai")
    evid(bot(A,-30),"user correction",470); evid(bot(S),"question and answer",440)
    evid((650,230),"retrieved context",500); evid(bot(C),"knowledge versions",470)
    evid(bot(M),"model and skill version",440); evid((1110,185),"query",500)
    evid(bot(L),"rows, snapshot, freshness",440); evid(bot(X),"reconciliation result",500)
else:
    out.clear(); start(1680,660)
    group(30,30,1620,380,"Coding Agents")
    A=box(60,140,170,90,[("Data Engineer","b"),("assigns a story","i")],"person")
    T=box(60,285,170,100,[("Story Tracker","b"),("scope, acceptance","i"),("criteria","i")])
    S=box(320,140,200,90,[("Plugin + Skill","b")])
    D=cyl(320,280,200,105,[("Local State","b"),("DRD, LLD, mapping, DQS","i")])
    Rp=box(610,140,180,90,[("Git Repo","b"),("pull request + diff","i")])
    CI=box(880,140,220,90,[("CI/CD","b"),("tests, validators, DQ checks","i")])
    AF=box(1190,140,180,90,[("Airflow","b"),("schedules the DAG","i")])
    L=cyl(1460,135,160,100,[("Lakehouse","b")])
    arrow([rt(A),lf(S)]); arrow([bot(A),top(T)])
    arrow([rt(T),(320,335)],label="reads",lpos=(275,315)); arrow([(420,280),(420,230)],label="reads",lpos=(470,256))
    arrow([rt(S),lf(Rp)],label="code",lpos=(565,165)); arrow([rt(Rp),lf(CI)]); arrow([rt(CI),lf(AF)],label="deploy",lpos=(1145,165))
    arrow([rt(AF),(1460,185)],label="run",lpos=(1415,165))
    ES=box(60,560,1560,70,[("Trace and Evidence Store","b"),("agent transcripts, CI logs, task logs, eval results","i")],"ai")
    evid(bot(T),"scope",470); evid(bot(D),"artifact revisions",500)
    arrow([(500,230),(500,255),(565,255),(565,560)],ai=True,dash=True,label=["run transcript,","model, skill, plugin"],lpos=(565,445))
    evid((665,230),"the diff",500); evid((745,230),"review comments",440)
    evid(bot(CI),"test and validator results",470)
    evid(bot(AF),"task failure",500); evid(bot(L),"data check results",440)
out.append("</svg>")
open(sys.argv[2],"w").write("\n".join(out))
