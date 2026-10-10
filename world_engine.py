import json, random, sqlite3, math
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'worlds.db'
PRODUCTS = ['Potion','Bread','Lantern','Apple','Map','Blanket','Toy Horse','Notebook','Blue Gem','Seed Pack','Milk','Cookies','Compass','Small Shield','Herb Bundle']

class WorldEngine:
    def __init__(self):
        self.sessions = {}
        self.home_sessions = {}
        self.decorator_sessions = {}
        self.init_db()
        self.ensure_prefabs()

    def init_db(self):
        con = sqlite3.connect(DB_PATH); c = con.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS worlds (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, data TEXT NOT NULL)')
        con.commit(); con.close()

    def ensure_prefabs(self):
        if self.list_worlds(): return
        for w in prefab_worlds(): self.save_world(w)

    def save_world(self, w):
        con = sqlite3.connect(DB_PATH); c = con.cursor()
        c.execute('INSERT INTO worlds (name,data) VALUES (?,?)', (w['name'], json.dumps(w)))
        con.commit(); wid = c.lastrowid; con.close(); return wid

    def update_world(self, wid, w):
        con = sqlite3.connect(DB_PATH); c = con.cursor()
        c.execute('UPDATE worlds SET name=?, data=? WHERE id=?', (w.get('name','World'), json.dumps(w), wid))
        con.commit(); con.close()

    def list_worlds(self):
        con = sqlite3.connect(DB_PATH); c = con.cursor(); c.execute('SELECT id,name FROM worlds ORDER BY id ASC')
        rows = c.fetchall(); con.close(); return rows

    def load_world(self, wid):
        con = sqlite3.connect(DB_PATH); c = con.cursor(); c.execute('SELECT data FROM worlds WHERE id=?',(wid,)); row = c.fetchone(); con.close()
        if not row: return None
        w = json.loads(row[0]); w['id'] = int(wid); normalize(w); return w

    def start_builder(self, user, mode):
        qs = world_questions(mode)
        self.sessions[user] = {'step':-1,'name':None,'answers':[],'questions':qs}
        return {'question':'Name your world:', 'options':[], 'input':'text'}

    def answer(self,user,choice):
        s = self.sessions.get(user)
        if not s: return {'error':'No active world forge.'}
        if s['step'] == -1:
            s['name'] = (choice or 'Unnamed World').strip(); s['step']=0; return s['questions'][0]
        s['answers'].append(choice); s['step'] += 1
        if s['step'] >= len(s['questions']):
            w = base_world(s['name'], s['answers'][0] if s['answers'] else 'Sanctuary Meadow')
            w['answers'] = s['answers']; wid = self.save_world(w); w['id']=wid; del self.sessions[user]
            return {'done':True,'world':w}
        return s['questions'][s['step']]

    def start_home_builder(self,user,mode):
        qs=[
            {'question':'Name this home:', 'options':[], 'input':'text'},
            {'question':'Home style?', 'options':['Cottage','Cabin','Townhouse','Safehouse','Shop Loft']},
            {'question':'Roof type?', 'options':['Dome','Gable','Flat','Tower','Mushroom Cap']},
            {'question':'Interior theme?', 'options':['Cozy','Library','Zelda Shop','Modern','Dream Room']},
            {'question':'Main color?', 'options':['Purple','Blue','Green','Amber','Rose']},
        ]
        self.home_sessions[user]={'step':0,'answers':[],'questions':qs}; return qs[0]

    def answer_home(self,user,choice,w):
        s=self.home_sessions.get(user)
        if not s: return {'error':'No active home forge.'}
        s['answers'].append(choice); s['step'] += 1
        if s['step'] >= len(s['questions']):
            a=s['answers']; h=default_home(a[0] or 'New Home', random.randint(-8,8), random.randint(-7,7))
            h['style']=a[1] if len(a)>1 else 'Cottage'; h['roof']=a[2] if len(a)>2 else 'Dome'; h['theme']=a[3] if len(a)>3 else 'Cozy'; h['color']=a[4] if len(a)>4 else 'Purple'
            w.setdefault('homes',[]).append(h); del self.home_sessions[user]; return {'done':True,'home':h,'world':w}
        return s['questions'][s['step']]

    def start_decorator(self,user,mode):
        count=10 if mode=='beginner' else (15 if mode=='medium' else 25)
        base=decorator_questions(); qs=[]
        while len(qs)<count: qs.extend(base)
        qs=qs[:count]; qs.append({'question':'Write 1-2 paragraphs describing the home:', 'options':[], 'input':'paragraph'})
        self.decorator_sessions[user]={'step':0,'answers':[],'questions':qs}; return qs[0]

    def answer_decorator(self,user,choice,w,home_index=0):
        s=self.decorator_sessions.get(user)
        if not s: return {'error':'No active decorator forge.'}
        s['answers'].append(choice); s['step'] += 1
        if s['step'] >= len(s['questions']):
            homes=w.setdefault('homes',[])
            if not homes: homes.append(default_home('Decorated Sanctuary Home',0,0))
            idx=max(0,min(int(home_index or 0),len(homes)-1)); h=homes[idx]
            paragraph=s['answers'][-1] if s['answers'] else ''
            h['paragraph']=paragraph; h['decor']=s['answers'][:10]; h['roof']='Dome' if 'dome' in paragraph.lower() else h.get('roof','Dome')
            h['furniture']=[{'type':'bed','x':-2,'z':-1},{'type':'table','x':0,'z':1},{'type':'shelf','x':2,'z':-1},{'type':'lamp','x':-2,'z':2},{'type':'plant','x':2,'z':2}]
            del self.decorator_sessions[user]; return {'done':True,'home':h,'world':w}
        return s['questions'][s['step']]

    def move(self,w,dest):
        if not w: return {'error':'No world loaded.'}
        cur=w.get('current_location','Entry Gate')
        if dest in w.get('nodes',{}).get(cur,[]): w['current_location']=dest; return w
        return {'error':'Invalid move.'}


def _distance_point_to_segment(px, pz, ax, az, bx, bz):
    dx = bx - ax; dz = bz - az
    if dx == 0 and dz == 0:
        return math.hypot(px - ax, pz - az)
    t = max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / (dx * dx + dz * dz)))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz))

def _near_line(w, x, z, line_type, radius):
    for group in ('roads', 'custom_builds'):
        for line in w.get(group, []):
            if line.get('type') != line_type:
                continue
            pts = line.get('points') or []
            for i in range(len(pts) - 1):
                ax, az = pts[i]; bx, bz = pts[i + 1]
                if _distance_point_to_segment(x, z, ax, az, bx, bz) <= radius:
                    return True
    return False

def _near_any_road(w, x, z):
    return any(_near_line(w, x, z, t, 3.25) for t in ('road', 'trail', 'path', 'bridge'))

def _near_power(w, x, z):
    return _near_line(w, x, z, 'powerline', 4.0)

def zone_capacity(zone):
    """How many structures a zone can eventually hold."""
    area = float(zone.get('w', 4)) * float(zone.get('d', 4))
    return max(1, int(area // 5))

def point_in_zone(x, zpos, zone):
    return (abs(x - float(zone.get('x', 0))) <= float(zone.get('w', 4))/2 and
            abs(zpos - float(zone.get('z', 0))) <= float(zone.get('d', 4))/2)

def occupied_points(w):
    pts=[]
    for key in ['homes','stores','industry','parks']:
        for item in w.get(key, []):
            pts.append((float(item.get('x', 0)), float(item.get('z', 0))))
    return pts

def zone_existing_count(w, zone):
    keys = {'residential':['homes'], 'commercial':['stores'], 'industrial':['industry']}.get(zone.get('type'), ['homes','stores','industry'])
    count=0
    for key in keys:
        for item in w.get(key, []):
            if point_in_zone(float(item.get('x', 0)), float(item.get('z', 0)), zone):
                count += 1
    return count

def find_open_lot(w, zone):
    occ=occupied_points(w)
    zx=float(zone.get('x', 0)); zz=float(zone.get('z', 0)); zw=float(zone.get('w', 4)); zd=float(zone.get('d', 4))
    candidates=[]
    step=2
    minx=math.ceil(zx-zw/2+1); maxx=math.floor(zx+zw/2-1)
    minz=math.ceil(zz-zd/2+1); maxz=math.floor(zz+zd/2-1)
    for x in range(minx, maxx+1, step):
        for z in range(minz, maxz+1, step):
            if all(math.hypot(x-ox, z-oz) >= 1.8 for ox,oz in occ):
                score = 0
                if _near_any_road(w, x, z): score -= 3
                if _near_power(w, x, z): score -= 2
                score += math.hypot(x-zx, z-zz)
                candidates.append((score, x, z))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1], candidates[0][2]

def recalc_city_stats(w):
    normalize(w)
    homes=w.get('homes', []); stores=w.get('stores', []); industry=w.get('industry', [])
    pop=sum(int(h.get('residents', 4)) for h in homes)
    jobs=sum(int(s.get('jobs', 3)) for s in stores) + sum(int(i.get('jobs', 6)) for i in industry)
    monthly_tax=round(pop*1.2 + jobs*2.0 + len(stores)*12 + len(industry)*18, 2)
    zone_stats=[]
    for z in w.get('zones', []):
        cap=zone_capacity(z); used=zone_existing_count(w, z)
        zone_stats.append({'type':z.get('type'), 'used':used, 'capacity':cap, 'empty':max(0, cap-used), 'road':_near_any_road(w, float(z.get('x',0)), float(z.get('z',0))), 'power':_near_power(w, float(z.get('x',0)), float(z.get('z',0)))})
    sim=w.setdefault('sim', {})
    sim.update({'population':pop, 'jobs':jobs, 'monthly_tax':monthly_tax, 'zone_stats':zone_stats})
    return sim

def city_demand(w):
    sim=recalc_city_stats(w)
    pop=sim.get('population', 0); jobs=sim.get('jobs', 0)
    home_capacity=max(1, len(w.get('homes', []))*4)
    r_zone_empty=sum(max(0, zone_capacity(z)-zone_existing_count(w,z)) for z in w.get('zones',[]) if z.get('type')=='residential')
    c_zone_empty=sum(max(0, zone_capacity(z)-zone_existing_count(w,z)) for z in w.get('zones',[]) if z.get('type')=='commercial')
    i_zone_empty=sum(max(0, zone_capacity(z)-zone_existing_count(w,z)) for z in w.get('zones',[]) if z.get('type')=='industrial')
    # Demand is intentionally simple and visible, like an early city builder.
    residential=min(100, max(15, 35 + jobs*3 - pop + r_zone_empty*7))
    commercial=min(100, max(5, 25 + pop//3 - len(w.get('stores',[]))*12 + c_zone_empty*5))
    industrial=min(100, max(5, 22 + pop//4 - len(w.get('industry',[]))*10 + i_zone_empty*5))
    return {'residential':residential, 'commercial':commercial, 'industrial':industrial}

def growth_chance(w, zone, demand):
    ztype=zone.get('type','residential')
    chance={'residential':0.20,'commercial':0.14,'industrial':0.13}.get(ztype,0.10)
    chance += demand.get(ztype, 0) / 180.0
    existing=zone_existing_count(w, zone)
    if existing == 0: chance += 0.16
    if _near_any_road(w, float(zone.get('x',0)), float(zone.get('z',0))): chance += 0.18
    if _near_power(w, float(zone.get('x',0)), float(zone.get('z',0))): chance += 0.12
    return min(0.92, chance)

def grow_one_lot(w, zone):
    lot=find_open_lot(w, zone)
    if not lot:
        return None
    x,z=lot
    ztype=zone.get('type', 'residential')
    sim=w.setdefault('sim', {})
    year=sim.get('year', 1); month=sim.get('month', 1)
    near_power=_near_power(w, x, z); near_road=_near_any_road(w, x, z)
    level=1 + int(near_power) + int(near_road)
    if ztype == 'residential':
        n=len(w.setdefault('homes', []))+1
        names=['Cabin','Small Home','Family House','Apartment']
        h=default_home(f'Auto {names[min(level,3)]} {n}', x, z)
        h.update({'auto_built': True, 'built_year': year, 'built_month': month, 'growth_level':level, 'residents':[3,4,6,12][min(level,3)], 'style':names[min(level,3)], 'color':['Green','Blue','Amber','Purple'][min(level,3)]})
        w['homes'].append(h); return {'type': ztype, 'name': h['name'], 'x': x, 'z': z}
    if ztype == 'commercial':
        n=len(w.setdefault('stores', []))+1
        names=['Kiosk','Corner Shop','Restaurant','Office']
        st=default_store(f'Auto {names[min(level,3)]} {n}', x, z)
        st.update({'auto_built': True, 'built_year': year, 'built_month': month, 'growth_level':level, 'jobs':[2,3,6,10][min(level,3)], 'roof':'Awning'})
        w['stores'].append(st); return {'type': ztype, 'name': st['name'], 'x': x, 'z': z}
    if ztype == 'industrial':
        n=len(w.setdefault('industry', []))+1
        names=['Shed','Workshop','Factory','Industrial Complex']
        ind={'name':f'Auto {names[min(level,3)]} {n}','x':x,'z':z,'auto_built':True,'built_year':year,'built_month':month,'growth_level':level,'jobs':[3,6,12,18][min(level,3)]}
        w.setdefault('industry', []).append(ind); return {'type': ztype, 'name': ind['name'], 'x': x, 'z': z}
    return None

def upgrade_existing_buildings(w, log):
    # Once connected to road and power, older buildings can slowly upgrade.
    for key, label, max_level in [('homes','home',3), ('stores','shop',3), ('industry','industry',3)]:
        for item in w.get(key, []):
            lvl=int(item.get('growth_level', 1))
            if lvl >= max_level: continue
            x=float(item.get('x',0)); z=float(item.get('z',0))
            if _near_any_road(w,x,z) and _near_power(w,x,z) and random.random() < 0.08:
                item['growth_level']=lvl+1
                if key=='homes': item['residents']=int(item.get('residents',4))+2
                elif key=='stores': item['jobs']=int(item.get('jobs',3))+2
                else: item['jobs']=int(item.get('jobs',6))+3
                log.append(f"Year {w['sim']['year']} Month {w['sim']['month']}: upgraded {item.get('name', label)} to level {lvl+1}.")

def simulate_growth(w, months=12):
    normalize(w)
    sim=w.setdefault('sim', {'year':1, 'month':1, 'population':0, 'jobs':0, 'log':[]})
    log=[]
    months=max(1, int(months or 1))
    for _ in range(months):
        sim['month'] += 1
        if sim['month'] > 12:
            sim['month'] = 1
            sim['year'] += 1
        demand=city_demand(w)
        sim['demand']=demand
        for zone in w.get('zones', []):
            cap=zone_capacity(zone)
            existing=zone_existing_count(w, zone)
            if existing >= cap:
                continue
            if random.random() <= growth_chance(w, zone, demand):
                built=grow_one_lot(w, zone)
                if built:
                    log.append(f"Year {sim['year']} Month {sim['month']}: built {built['name']} in {built['type']} zone at ({built['x']},{built['z']}).")
        upgrade_existing_buildings(w, log)
    demand=city_demand(w)
    sim['demand']=demand
    sim.setdefault('treasury', 0)
    sim['treasury']=round(float(sim.get('treasury',0)) + float(sim.get('monthly_tax',0)) * months, 2)
    sim.setdefault('log', []).extend(log)
    sim['log'] = sim['log'][-60:]
    return {'world': w, 'built': log, 'demand': demand, 'summary': f"Advanced {months} month(s). Built/upgraded {len(log)} lot event(s). Year {sim['year']}, Month {sim['month']}. Pop {sim.get('population',0)}, Jobs {sim.get('jobs',0)}, Treasury ${sim.get('treasury',0)}."}

def world_questions(mode):
    return [
        {'question':'World Type?', 'options':['Sanctuary Meadow','Voxel City','Forest Village','Ocean Edge','Lakeside Cottage']},
        {'question':'Lighting?', 'options':['Morning Glow','Sunny Day','Neon Dusk','Soft Night','Dream Fog']},
        {'question':'Water Feature?', 'options':['Stream','Lake','Ocean Edge','Pond','None']},
        {'question':'Main Path Style?', 'options':['Road','Trail','Stone Path','Boardwalk','Brick Street']},
        {'question':'Safe Feeling?', 'options':['Cozy','Protected','Open','Magical','Quiet']},
    ]

def decorator_questions():
    return [
        {'question':'Overall vibe?', 'options':['Cozy','Magical','Roblox Bright','Zelda Village','Modern Sanctuary']},
        {'question':'Room shape?', 'options':['Square','Long Hall','Round/Domed','Split Level','Open Studio']},
        {'question':'Wall color?', 'options':['Warm Wood','Soft Blue','Green Meadow','Purple Dream','Golden Sand']},
        {'question':'Lighting?', 'options':['Lanterns','Sunbeams','Neon Glow','Fireplace','Moon Lamps']},
        {'question':'Main furniture?', 'options':['Bed','Couch','Table','Bookshelf','Kitchen Counter']},
    ]

def base_world(name, kind):
    return {
        'name':name,'kind':kind,'current_location':'Entry Gate',
        'planet': {'lat': random.uniform(-45,45), 'lon': random.uniform(-120,120)},
        'nodes':{'Entry Gate':['Main Path'],'Main Path':['Entry Gate','Home Circle','Market Row','Lake Path','Industrial Corner'],'Home Circle':['Main Path','Cozy Home'],'Cozy Home':['Home Circle'],'Market Row':['Main Path','Convenience Store'],'Convenience Store':['Market Row'],'Lake Path':['Main Path','Lake Edge'],'Lake Edge':['Lake Path'],'Industrial Corner':['Main Path']},
        'roads':[{'type':'road','points':[[0,9],[0,0],[6,-2]],'width':1.3},{'type':'trail','points':[[0,0],[-5,-2]],'width':0.55}],
        'zones':[{'type':'residential','x':-6,'z':-2,'w':5,'d':5},{'type':'commercial','x':6,'z':-2,'w':5,'d':5},{'type':'industrial','x':-7,'z':6,'w':4,'d':4}],
        'water':[{'type':'stream','x':-8,'z':2,'w':2,'d':16},{'type':'lake','x':7,'z':-8,'r':3.2},{'type':'ocean','x':0,'z':-16,'w':34,'d':4}],
        'trees':default_trees(), 'homes':[default_home('Cozy Home',-5,-2), default_home('Guest Cottage',3,4)],
        'stores':[default_store('Convenience Store',6,-2)], 'industry':[{'name':'Ryoko Relay Workshop','x':-7,'z':6}],
        'parks':[{'name':'Pocket Park','x':-2,'z':4}], 'lamps':[{'x':0,'z':4},{'x':2,'z':1},{'x':6,'z':-3}],
        'npcs':[{'name':'Path Runner','route':[[0,8],[0,0],[6,-2]],'emoji':'🏃'}], 'sim':{'year':1,'month':1,'population':8,'jobs':8,'log':[]}, 'custom_builds':[]
    }

def normalize(w):
    for k in ['zones','industry','parks','lamps','custom_builds','homes','stores','trees','water','roads']:
        w.setdefault(k, [])
    w.setdefault('planet', {'lat':0,'lon':0})
    w.setdefault('sim', {'year':1, 'month':1, 'population':len(w.get('homes', []))*4, 'jobs':len(w.get('stores', []))*3+len(w.get('industry', []))*5, 'log':[]})

def default_home(name,x,z):
    return {'name':name,'x':x,'z':z,'style':'Cottage','roof':'Dome','theme':'Cozy','color':'Purple','furniture':[],'decor':['lantern','plant']}

def default_store(name,x,z):
    return {'name':name,'x':x,'z':z,'products':PRODUCTS[:],'shelves':4,'counter':True,'roof':'Awning'}

def default_trees():
    return [{'x':-9,'z':-7},{'x':-10,'z':1},{'x':-8,'z':7},{'x':9,'z':4},{'x':10,'z':-5},{'x':3,'z':8},{'x':-3,'z':-8}]

def prefab_worlds():
    names=['Meadow Home Sanctuary','Lakeside Cottage World','Little City Market','Forest Trail Village','Ocean Edge Safehouse']
    kinds=['Sanctuary Meadow','Lakeside Cottage','Voxel City','Forest Village','Ocean Edge']
    return [base_world(n,k) for n,k in zip(names,kinds)]
