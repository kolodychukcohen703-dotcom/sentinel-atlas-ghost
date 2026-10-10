from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from world_engine import WorldEngine, default_home, default_store, simulate_growth, recalc_city_stats, city_demand
from sentinel_kelowna import kelowna_bp, init_db, ensure_map_cache
import random, time, os

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sentinel-atlas-local'
app.register_blueprint(kelowna_bp, url_prefix='/kelowna')
with app.app_context():
    init_db()
engine = WorldEngine()
current_world = None
current_world_id = None
player_inventory = []
selected_home = 0

@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/collaboration')
def collaboration_status():
    return jsonify({'ok': True,
                    'atlas': request.host_url.rstrip('/'),
                    'ghost_hub': os.environ.get('GHOST_HUB_URL', 'http://127.0.0.1:5011'),
                    'world_count': len(engine.list_worlds())})

def save_current():
    if current_world and current_world_id: engine.update_world(current_world_id, current_world)

@app.route('/start', methods=['POST'])
def start(): return jsonify(engine.start_builder('user', request.json.get('mode','beginner')))
@app.route('/answer', methods=['POST'])
def answer(): return jsonify(engine.answer('user', request.json.get('choice','')))
@app.route('/worlds')
def worlds(): return jsonify(engine.list_worlds())
@app.route('/load', methods=['POST'])
def load():
    global current_world,current_world_id
    current_world_id=int(request.json.get('id')); current_world=engine.load_world(current_world_id)
    return jsonify(current_world or {'error':'World not found'})
@app.route('/move', methods=['POST'])
def move():
    global current_world
    result=engine.move(current_world, request.json.get('dest'))
    if 'error' not in result: current_world=result; save_current()
    return jsonify(result)
@app.route('/build', methods=['POST'])
def build():
    global current_world
    if not current_world: return jsonify({'error':'Load a world first.'})
    item=request.json or {}; kind=item.get('type','path'); x=int(round(float(item.get('x',0)))); z=int(round(float(item.get('z',0))))
    if kind in ('road','trail','path','bridge','rail','powerline'): current_world.setdefault('custom_builds',[]).append(item)
    elif kind=='tree': current_world.setdefault('trees',[]).append({'x':x,'z':z})
    elif kind=='water': current_world.setdefault('water',[]).append({'type':'stream','x':x,'z':z,'w':2,'d':8})
    elif kind=='lake': current_world.setdefault('water',[]).append({'type':'lake','x':x,'z':z,'r':3})
    elif kind=='shop': current_world.setdefault('stores',[]).append(default_store('New Shop',x,z))
    elif kind=='home': current_world.setdefault('homes',[]).append(default_home('New Home',x,z))
    elif kind=='industry': current_world.setdefault('industry',[]).append({'name':'Workshop','x':x,'z':z})
    elif kind=='park': current_world.setdefault('parks',[]).append({'name':'Pocket Park','x':x,'z':z}); current_world.setdefault('trees',[]).extend([{'x':x-1,'z':z},{'x':x+1,'z':z},{'x':x,'z':z+1}])
    elif kind=='lamp': current_world.setdefault('lamps',[]).append({'x':x,'z':z})
    elif kind in ('residential_zone','commercial_zone','industrial_zone'): current_world.setdefault('zones',[]).append({'type':kind.replace('_zone',''),'x':x,'z':z,'w':4,'d':4})
    save_current(); return jsonify(current_world)
@app.route('/simulate', methods=['POST'])
def simulate():
    global current_world
    if not current_world: return jsonify({'error':'Load a world first.'})
    months=int((request.json or {}).get('months',12))
    result=simulate_growth(current_world, months)
    current_world=result['world']; save_current()
    return jsonify(result)

@app.route('/undo_build', methods=['POST'])
def undo_build():
    global current_world
    if current_world:
        for key in ['custom_builds','zones','lamps','parks','industry','stores','homes','water','trees']:
            if current_world.get(key): current_world[key].pop(); break
        save_current()
    return jsonify(current_world or {})
@app.route('/clear_builds', methods=['POST'])
def clear_builds():
    global current_world
    if current_world: current_world['custom_builds']=[]; current_world['zones']=[]; save_current()
    return jsonify(current_world or {})
@app.route('/home/start', methods=['POST'])
def home_start(): return jsonify(engine.start_home_builder('user', request.json.get('mode','beginner')))
@app.route('/home/answer', methods=['POST'])
def home_answer():
    global current_world
    if not current_world: return jsonify({'error':'Load a world first.'})
    result=engine.answer_home('user', request.json.get('choice',''), current_world)
    if result.get('done'): current_world=result['world']; save_current()
    return jsonify(result)
@app.route('/decorator/start', methods=['POST'])
def decorator_start(): return jsonify(engine.start_decorator('user', request.json.get('mode','beginner')))
@app.route('/decorator/answer', methods=['POST'])
def decorator_answer():
    global current_world
    if not current_world: return jsonify({'error':'Load a world first.'})
    result=engine.answer_decorator('user', request.json.get('choice',''), current_world, selected_home)
    if result.get('done'): current_world=result['world']; save_current()
    return jsonify(result)
@app.route('/ryoko_status')
def ryoko_status():
    rsrp=random.randint(-118,-84); sinr=round(random.uniform(1,22),1); health='good' if rsrp>=-95 and sinr>=13 else ('warning' if rsrp>=-110 and sinr>=5 else 'bad')
    return jsonify({'source':'simulated-safe','online':False,'timestamp':time.strftime('%Y-%m-%d %H:%M:%S'),'rsrp':rsrp,'sinr':sinr,'health':health})

def products():
    if not current_world: return []
    return [(s.get('name','Shop'),p) for s in current_world.get('stores',[]) for p in s.get('products',[])]
@app.route('/chat', methods=['POST'])
def chat():
    global current_world,current_world_id,player_inventory,selected_home
    msg=(request.json.get('message') or '').strip(); low=msg.lower()
    if low in ('!help','help'): return jsonify({'reply':'Commands: !stars, !planet, !city, !bird, !street, !worlds, !enter <id>, !homes, !selecthome <n>, !decorator beginner|medium|advanced, !shop, !buy <product>, !inventory, !simulate year, !simulate month, !stats'})
    if low in ('!stars','!star','!starchart'): return jsonify({'reply':'Opening 3D Star Chart.', 'view':'stars'})
    if low=='!planet': return jsonify({'reply':'Opening Planet View.', 'view':'planet'})
    if low=='!city': return jsonify({'reply':'Opening City View.', 'view':'city'})
    if low=='!bird': return jsonify({'reply':'Opening Bird Grid View.', 'view':'bird'})
    if low=='!street': return jsonify({'reply':'Opening Street View.', 'view':'street'})
    if low=='!worlds': return jsonify({'reply':'Worlds:\n'+'\n'.join([f'#{i} {n}' for i,n in engine.list_worlds()])})
    if low.startswith('!enter'):
        try:
            wid=int(low.split()[1]); current_world_id=wid; current_world=engine.load_world(wid); return jsonify({'reply':f'Entered #{wid}: {current_world.get("name") if current_world else "not found"}', 'world':current_world})
        except Exception: return jsonify({'reply':'Usage: !enter <id>'})
    if low=='!homes':
        if not current_world: return jsonify({'reply':'No world loaded.'})
        return jsonify({'reply':'Homes:\n'+'\n'.join([f'{i}: {h.get("name","Home")}' for i,h in enumerate(current_world.get('homes',[]))])})
    if low.startswith('!selecthome'):
        try: selected_home=int(low.split()[1]); return jsonify({'reply':f'Selected home {selected_home}.'})
        except Exception: return jsonify({'reply':'Usage: !selecthome <number>'})
    if low.startswith('!decorator'): return jsonify({'reply':'Use Decorator Forge buttons, or the left panel, to continue the questionnaire.'})
    if low=='!shop': return jsonify({'reply':'Available products:\n'+'\n'.join([f'{s}: {p}' for s,p in products()]) if products() else 'No products.'})
    if low.startswith('!buy '):
        product=msg[5:].strip()
        if product.lower() in [p.lower() for _,p in products()]: player_inventory.append(product); return jsonify({'reply':f'Bought: {product}'})
        return jsonify({'reply':'Could not find that product. Type !shop.'})
    if low=='!inventory': return jsonify({'reply':'Inventory:\n'+'\n'.join(player_inventory) if player_inventory else 'Inventory is empty.'})
    if low=='!stats':
        if not current_world: return jsonify({'reply':'Load a world first.'})
        sim=recalc_city_stats(current_world); dem=city_demand(current_world); save_current()
        zones='\n'.join([f"{z.get('type')}: {z.get('used')}/{z.get('capacity')} road={z.get('road')} power={z.get('power')}" for z in sim.get('zone_stats',[])])
        return jsonify({'reply':f"City Stats\nYear {sim.get('year',1)} Month {sim.get('month',1)}\nPopulation: {sim.get('population',0)}\nJobs: {sim.get('jobs',0)}\nMonthly tax: ${sim.get('monthly_tax',0)}\nTreasury: ${sim.get('treasury',0)}\nDemand R/C/I: {dem.get('residential',0)}/{dem.get('commercial',0)}/{dem.get('industrial',0)}\n{zones}", 'world':current_world})
    if low in ('!simulate year','!grow year','!year'):
        if not current_world: return jsonify({'reply':'Load a world first.'})
        result=simulate_growth(current_world, 12); save_current(); return jsonify({'reply':result['summary']+'\n'+('\n'.join(result['built'][-8:]) if result['built'] else 'No new lots this time.'), 'world':current_world})
    if low in ('!simulate month','!grow month','!month'):
        if not current_world: return jsonify({'reply':'Load a world first.'})
        result=simulate_growth(current_world, 1); save_current(); return jsonify({'reply':result['summary']+'\n'+('\n'.join(result['built'][-4:]) if result['built'] else 'No new lots this month.'), 'world':current_world})
    return jsonify({'reply':'Sentinel heard: '+msg})

if __name__=='__main__':
    try: ensure_map_cache()
    except Exception as exc: print('Map cache unavailable; continuing offline:', exc)
    app.run(host='127.0.0.1', port=5010, debug=False)
