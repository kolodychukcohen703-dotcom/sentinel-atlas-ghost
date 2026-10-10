
let sentinelStreetView=null;
let sentinelStreetAnnotations=[];
let sentinelStreetMarkers=[];
let sentinelStreetPinsVisible=true;
let sentinelStreetInfoWindow=null;
window.sentinelInitGoogleMaps=function(){tryInitStreetView();};

function tryInitStreetView(){
  const pane=document.getElementById("streetViewCanvas");
  const noKey=document.getElementById("streetNoKey");
  const status=document.getElementById("streetStatus");
  if(!window.SENTINEL_GOOGLE_MAPS_API_KEY){
    if(noKey) noKey.hidden=false;
    if(status) status.textContent="API key missing";
    return;
  }
  if(!window.google || !google.maps || !google.maps.StreetViewPanorama){
    if(status) status.textContent="Google Maps loading…";
    return;
  }
  if(noKey) noKey.hidden=true;
  if(!sentinelStreetView){
    sentinelStreetView=new google.maps.StreetViewPanorama(pane,{
      position:{lat:49.8879,lng:-119.4960},
      pov:{heading:0,pitch:0}, zoom:1,
      addressControl:true, fullscreenControl:true,
      linksControl:true, panControl:true, zoomControl:true
    });
    sentinelStreetView.addListener("position_changed",()=>{
      const p=sentinelStreetView.getPosition();
      if(p && status) status.textContent=`${p.lat().toFixed(6)}, ${p.lng().toFixed(6)}`;
      updateAnnotationPositionPreview();
    });
    sentinelStreetView.addListener("pov_changed",updateAnnotationPositionPreview);
    loadStreetAnnotations();
  }
}
function setStreetPosition(lat,lng,heading=0){
  tryInitStreetView();
  if(!sentinelStreetView) return;
  sentinelStreetView.setPosition({lat,lng});
  sentinelStreetView.setPov({heading,pitch:0});
}

const $=s=>document.querySelector(s);
const SVG="http://www.w3.org/2000/svg";
const state={fc:null,netNodes:[],netLinks:[],mode:"cad",bounds:null};
const layerDefs=[
 ["WATER","Water","gWater"],["LANDUSE","Land Use","gLanduse"],["ROADS","Roads","gRoads"],
 ["PATHS","Paths / Sidewalks","gPaths"],["RAIL","Rail","gRail"],["BUILDINGS","Buildings","gBuildings"],
 ["TRANSIT","Transit Stops","gTransit"],["TRAFFIC","Traffic Signals","gTraffic"],["AMENITIES","Amenities","gAmenities"],
 ["SENTINEL","Sentinel Objects","gSentinel"]
];
const netLayerDefs=[
 ["NET_PHYSICAL","Physical Cable / Conduit","gNetPhysical"],
 ["NET_LOGICAL","Logical Network","gNetLogical"],
 ["WIFI_COVERAGE","Wi‑Fi Coverage","gWifi"],
 ["PBX_TERMINALS","PBX / Kiosk","gPbx"]
];
async function api(path,opts={}){let r=await fetch(path,{headers:{"Content-Type":"application/json"},...opts});let j=await r.json();if(!r.ok)throw Error(j.error||"request failed");return j}
function svg(tag,attrs={}){let e=document.createElementNS(SVG,tag);for(let[k,v]of Object.entries(attrs))e.setAttribute(k,v);return e}
function makeLayerUI(){
 layers.innerHTML=layerDefs.map(x=>`<label class="layer-row"><input type="checkbox" data-g="${x[2]}" checked> ${x[1]}</label>`).join("");
 netLayers.innerHTML=netLayerDefs.map(x=>`<label class="layer-row"><input type="checkbox" data-g="${x[2]}" checked> ${x[1]}</label>`).join("");
 document.querySelectorAll("[data-g]").forEach(c=>c.addEventListener("change",()=>{$("#"+c.dataset.g).style.display=c.checked?"":"none"}));
}
function calcBounds(fc){
 let xs=[],ys=[]; for(let f of fc.features){let g=f.geometry;if(!g)continue;let c=g.coordinates;
 const scan=a=>{if(typeof a[0]==="number"){xs.push(a[0]);ys.push(a[1])}else a.forEach(scan)};scan(c)}
 if(!xs.length)return[-119.51,49.875,-119.48,49.9];return[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)]
}
function project(coord){
 let [minx,miny,maxx,maxy]=state.bounds; let pad=30;
 return [pad+(coord[0]-minx)/(maxx-minx)*(1200-pad*2), 800-pad-(coord[1]-miny)/(maxy-miny)*(800-pad*2)]
}
function pathD(coords){
 return coords.map((c,i)=>{let p=project(c);return`${i?"L":"M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`}).join(" ")
}
function renderMap(){
 document.querySelectorAll("#canvas g").forEach(g=>g.innerHTML="");
 if(!state.fc)return;
 state.bounds=calcBounds(state.fc);
 for(let f of state.fc.features){
   let layer=f.properties?.layer, geom=f.geometry; if(!geom)continue;
   let target={
    WATER:"gWater",LANDUSE:"gLanduse",ROADS:"gRoads",PATHS:"gPaths",RAIL:"gRail",
    BUILDINGS:"gBuildings",TRANSIT:"gTransit",TRAFFIC:"gTraffic",AMENITIES:"gAmenities"
   }[layer]; if(!target)continue; let g=$("#"+target);
   if(geom.type==="LineString"){
      let cls=layer==="ROADS"?"road":layer==="PATHS"?"path":layer==="RAIL"?"rail":"road";
      g.appendChild(svg("path",{d:pathD(geom.coordinates),class:cls}));
   } else if(geom.type==="Polygon"){
      let cls=layer==="BUILDINGS"?"building":layer==="WATER"?"water":"landuse";
      let p=svg("path",{d:pathD(geom.coordinates[0])+" Z",class:cls});g.appendChild(p);
   } else if(geom.type==="Point"){
      let p=project(geom.coordinates);g.appendChild(svg("circle",{cx:p[0],cy:p[1],r:layer==="TRAFFIC"?3:2.5,class:layer==="TRAFFIC"?"traffic":"point"}));
   }
 }
 renderNetwork();
}
function renderNetwork(){
 gNetLogical.innerHTML="";gWifi.innerHTML="";gPbx.innerHTML="";gNetPhysical.innerHTML="";
 let byId=Object.fromEntries(state.netNodes.map(n=>[n.id,n]));
 const np=n=>[600+(+n.x_m||0)*.8,400-(+n.y_m||0)*.8];
 for(let l of state.netLinks){let a=byId[l.a_id],b=byId[l.b_id];if(!a||!b)continue;let pa=np(a),pb=np(b);
   let target=(l.layer_name==="NET_PHYSICAL"||l.link_type==="conduit"||l.link_type==="fibre")?gNetPhysical:gNetLogical;
   target.appendChild(svg("line",{x1:pa[0],y1:pa[1],x2:pb[0],y2:pb[1],class:target===gNetPhysical?"net-physical":"net-link"}))
 }
 for(let n of state.netNodes){let p=np(n),target=n.node_type==="wifi_ap"?gWifi:(n.node_type==="pbx"||n.node_type==="kiosk"?gPbx:gNetLogical);
   if(n.node_type==="wifi_ap"){target.appendChild(svg("circle",{cx:p[0],cy:p[1],r:70,class:"wifi"}))}
   target.appendChild(svg("rect",{x:p[0]-8,y:p[1]-8,width:16,height:16,class:(target===gPbx?"pbx":"net-node")}));
   let t=svg("text",{x:p[0]+12,y:p[1]+4,fill:"currentColor","font-size":"11"});t.textContent=n.name;target.appendChild(t)
 }
 updateLinkSelects();
}
function updateLinkSelects(){
 let options=state.netNodes.map(n=>`<option value="${n.id}">${n.name}</option>`).join("");linkA.innerHTML=options;linkB.innerHTML=options
}
async function loadAll(){
 makeLayerUI();
 try{
   state.fc=await api("/kelowna/api/map");
   renderMap();
   let meta=await api("/kelowna/api/map/meta");sourceInfo.textContent=`${meta.source||""} ${meta.license||""} · features ${meta.features??state.fc.features.length}`;
   mapStatus.textContent=state.fc.features.length?`REAL MAP: ${state.fc.features.length} FEATURES`:"MAP NOT DOWNLOADED";
 }catch(e){mapStatus.textContent="MAP OFFLINE";sourceInfo.textContent=e.message}
 state.netNodes=await api("/kelowna/api/network/nodes");state.netLinks=await api("/kelowna/api/network/links");renderNetwork()
}
refreshMap.addEventListener("click",async()=>{mapStatus.textContent="DOWNLOADING…";try{let j=await api("/kelowna/api/map/refresh",{method:"POST",body:"{}"});if(!j.ok)throw Error(j.error);await loadAll()}catch(e){mapStatus.textContent="DOWNLOAD FAILED";sourceInfo.textContent=e.message}});
document.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>{document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");state.mode=b.dataset.mode;parallel.hidden=state.mode!=="parallel";street.hidden=state.mode!=="street";addressBuild.hidden=state.mode!=="addressbuild";worldBuilder.hidden=state.mode!=="worldbuilder";sanctuary.hidden=state.mode!=="sanctuary";if(window.journey)window.journey.hidden=state.mode!=="journey";canvas.hidden=["parallel","street","addressbuild","worldbuilder","sanctuary","journey"].includes(state.mode);if(state.mode==="street")setTimeout(tryInitStreetView,50);if(state.mode==="sanctuary")setTimeout(()=>window.renderSanctuaryRoom?.(),50)}));
document.querySelectorAll("[data-net]").forEach(b=>b.addEventListener("click",()=>{netType.value=b.dataset.net==="fibre"||b.dataset.net==="conduit"?"router":b.dataset.net;netName.value="New "+b.textContent.trim()}));
addNetNode.addEventListener("click",async()=>{await api("/kelowna/api/network/nodes",{method:"POST",body:JSON.stringify({name:netName.value,node_type:netType.value,address:netAddress.value,pbx_extension:netExt.value,vlan:netVlan.value,ssid:netSsid.value,x_m:(Math.random()-.5)*500,y_m:(Math.random()-.5)*350,layer_name:netType.value==="wifi_ap"?"WIFI_COVERAGE":(netType.value==="pbx"||netType.value==="kiosk"?"PBX_TERMINALS":"NET_LOGICAL")})});state.netNodes=await api("/kelowna/api/network/nodes");renderNetwork()});
addLink.addEventListener("click",async()=>{await api("/kelowna/api/network/links",{method:"POST",body:JSON.stringify({a_id:+linkA.value,b_id:+linkB.value,link_type:linkType.value,capacity:capacity.value,layer_name:(linkType.value==="fibre"||linkType.value==="conduit")?"NET_PHYSICAL":"NET_LOGICAL",label:linkType.value})});state.netLinks=await api("/kelowna/api/network/links");renderNetwork()});
canvas.addEventListener("mousemove",e=>{let r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*1200-600,y=400-(e.clientY-r.top)/r.height*800;cursor.textContent=`X ${x.toFixed(2)} Y ${y.toFixed(2)}`});
loadAll();

const sd=document.getElementById("streetDowntown");
const sq=document.getElementById("streetQueensway");
const sm=document.getElementById("streetMission");
const ep=document.getElementById("enterParallel");
if(sd) sd.addEventListener("click",()=>setStreetPosition(49.8879,-119.4960,0));
if(sq) sq.addEventListener("click",()=>setStreetPosition(49.8891,-119.4954,90));
if(sm) sm.addEventListener("click",()=>setStreetPosition(49.8550,-119.4890,180));
if(ep) ep.addEventListener("click",()=>{
  document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));
  const t=document.querySelector('.tab[data-mode="parallel"]');
  if(t) t.classList.add("active");
  state.mode="parallel"; parallel.hidden=false; street.hidden=true; canvas.hidden=true;
});


function annotationIcon(type){
  return {note:"📝",instruction:"📋",doorway:"🚪",pbx:"☎",object:"◆",waypoint:"📍",task:"✓",warning:"⚠",character:"☻"}[type]||"📍";
}
function escapeAnnotation(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}

async function loadStreetAnnotations(){
  sentinelStreetAnnotations=await api("/kelowna/api/street-annotations");
  renderStreetAnnotationMarkers(); renderAnnotationList();
}
function clearStreetMarkers(){sentinelStreetMarkers.forEach(m=>m.setMap(null));sentinelStreetMarkers=[];}
function renderStreetAnnotationMarkers(){
  clearStreetMarkers();
  if(!sentinelStreetView||!window.google||!sentinelStreetPinsVisible)return;
  if(!sentinelStreetInfoWindow) sentinelStreetInfoWindow=new google.maps.InfoWindow();
  sentinelStreetAnnotations.forEach(a=>{
    const m=new google.maps.Marker({
      position:{lat:Number(a.lat),lng:Number(a.lon)},
      map:sentinelStreetView,title:a.title,
      label:{text:annotationIcon(a.annotation_type),fontSize:"18px"}
    });
    m.addListener("click",()=>{
      sentinelStreetInfoWindow.setContent(`<div style="max-width:280px;color:#111">
        <strong>${annotationIcon(a.annotation_type)} ${escapeAnnotation(a.title)}</strong>
        <div>${escapeAnnotation(a.annotation_type)}</div>
        ${a.note?`<div><b>Note:</b> ${escapeAnnotation(a.note)}</div>`:""}
        ${a.instructions?`<div><b>Instructions:</b> ${escapeAnnotation(a.instructions)}</div>`:""}
        ${a.target?`<div><b>Target:</b> ${escapeAnnotation(a.target)}</div>`:""}
      </div>`);
      sentinelStreetInfoWindow.open({map:sentinelStreetView,anchor:m});
    });
    sentinelStreetMarkers.push(m);
  });
}
function currentStreetAnnotationPosition(){
  if(!sentinelStreetView)return null;
  const p=sentinelStreetView.getPosition(), pov=sentinelStreetView.getPov();
  if(!p)return null;
  return {lat:p.lat(),lon:p.lng(),pano_id:sentinelStreetView.getPano()||null,
    heading:Number(pov?.heading||0),pitch:Number(pov?.pitch||0),zoom:Number(sentinelStreetView.getZoom()||1)};
}
function updateAnnotationPositionPreview(){
  const el=document.getElementById("annPosition"),p=currentStreetAnnotationPosition();
  if(!el)return;
  el.textContent=p?`Pin: ${p.lat.toFixed(6)}, ${p.lon.toFixed(6)} · heading ${p.heading.toFixed(1)}° · pitch ${p.pitch.toFixed(1)}°`:
    "Open Street View and move to the point of interest.";
}
async function saveCurrentStreetPin(){
  const pos=currentStreetAnnotationPosition();
  if(!pos){alert("Open Street View first.");return;}
  await api("/kelowna/api/street-annotations",{method:"POST",body:JSON.stringify({
    ...pos,title:annTitle.value||"Sentinel Point of Interest",annotation_type:annType.value,
    note:annNote.value,instructions:annInstructions.value,action:annAction.value,target:annTarget.value,
    layer_name:"STREET_ANNOTATIONS"
  })});
  await loadStreetAnnotations();
}
function renderAnnotationList(){
  if(!annotationList)return;
  annotationList.innerHTML=sentinelStreetAnnotations.map(a=>`<div class="annotation-row">
    <strong>${annotationIcon(a.annotation_type)} ${escapeAnnotation(a.title)}</strong>
    <div class="meta">${Number(a.lat).toFixed(5)}, ${Number(a.lon).toFixed(5)} · ${escapeAnnotation(a.annotation_type)}</div>
    <div>${escapeAnnotation(a.note||a.instructions||"")}</div>
    <button data-go="${a.id}">Go</button><button data-del="${a.id}">Delete</button></div>`).join("")||'<div class="muted">No Street View pins yet.</div>';
  annotationList.querySelectorAll("[data-go]").forEach(b=>b.addEventListener("click",()=>{
    const a=sentinelStreetAnnotations.find(x=>x.id===Number(b.dataset.go)); if(!a)return;
    document.querySelector('.tab[data-mode="street"]')?.click();
    setTimeout(()=>{tryInitStreetView();if(sentinelStreetView){
      if(a.pano_id)sentinelStreetView.setPano(a.pano_id);else sentinelStreetView.setPosition({lat:Number(a.lat),lng:Number(a.lon)});
      sentinelStreetView.setPov({heading:Number(a.heading||0),pitch:Number(a.pitch||0)});sentinelStreetView.setZoom(Number(a.zoom||1));
    }},120);
  }));
  annotationList.querySelectorAll("[data-del]").forEach(b=>b.addEventListener("click",async()=>{
    if(confirm("Delete this Sentinel Street View pin?")){
      await api(`/kelowna/api/street-annotations/${b.dataset.del}`,{method:"DELETE"});await loadStreetAnnotations();
    }
  }));
}
dropStreetPin?.addEventListener("click",()=>{updateAnnotationPositionPreview();annTitle?.focus();});
saveStreetPin?.addEventListener("click",saveCurrentStreetPin);
toggleStreetPins?.addEventListener("click",()=>{sentinelStreetPinsVisible=!sentinelStreetPinsVisible;renderStreetAnnotationMarkers();});


let currentBuildLocation=null;
let buildProjects=[];

async function geocodeBuildAddress(){
  const addr=buildAddress.value.trim();
  if(!addr){geocodeResult.textContent="Enter an address.";return;}
  if(!window.google || !google.maps){
    geocodeResult.textContent="Google Maps has not loaded yet.";
    return;
  }
  try{
    const geocoder=new google.maps.Geocoder();
    const response=await geocoder.geocode({
      address:addr,
      componentRestrictions:{country:"CA"}
    });
    if(!response.results?.length){
      geocodeResult.textContent="No address result found.";
      return;
    }
    const r=response.results[0], p=r.geometry.location;
    currentBuildLocation={
      address:r.formatted_address,
      lat:p.lat(),
      lon:p.lng(),
      place_id:r.place_id || null
    };
    buildAddress.value=r.formatted_address;
    geocodeResult.textContent=`${r.formatted_address} · ${p.lat().toFixed(6)}, ${p.lng().toFixed(6)}`;
    setStreetPosition(p.lat(),p.lng(),0);
    generateAddressBlueprint();
    renderAddressStructure3D();
  }catch(e){
    geocodeResult.textContent="Address lookup failed: "+e.message;
  }
}

function buildParams(){
  return {
    width:Math.max(2,Number(buildWidth.value)||12),
    depth:Math.max(2,Number(buildDepth.value)||10),
    floors:Math.max(1,Number(buildFloors.value)||2),
    floorHeight:Math.max(2,Number(buildFloorHeight.value)||3),
    rotation:Number(buildRotation.value)||0,
    roof:buildRoof.value||"flat"
  };
}

function generateAddressBlueprint(){
  if(!window.addressPlan) return;
  const p=buildParams();
  const scale=Math.min(520/p.width,360/p.depth);
  const w=p.width*scale,d=p.depth*scale;
  const cx=450,cy=310,x=cx-w/2,y=cy-d/2;

  let inner="";
  const rooms=Math.max(2,Math.min(6,Math.round(p.width/4)));
  for(let i=1;i<rooms;i++){
    const xx=x+w*i/rooms;
    inner+=`<line x1="${xx}" y1="${y}" x2="${xx}" y2="${y+d}" class="plan-inner"/>`;
  }
  const hallY=y+d*.55;
  inner+=`<line x1="${x}" y1="${hallY}" x2="${x+w}" y2="${hallY}" class="plan-inner"/>`;

  addressPlan.setAttribute("transform",`rotate(${p.rotation} ${cx} ${cy})`);
  addressPlan.innerHTML=`
    <rect x="${x}" y="${y}" width="${w}" height="${d}" class="plan-wall"/>
    ${inner}
    <line x1="${x}" y1="${y-28}" x2="${x+w}" y2="${y-28}" class="plan-dim"/>
    <line x1="${x}" y1="${y-38}" x2="${x}" y2="${y-18}" class="plan-dim"/>
    <line x1="${x+w}" y1="${y-38}" x2="${x+w}" y2="${y-18}" class="plan-dim"/>
    <text x="${cx-25}" y="${y-36}" class="plan-dim-text">${p.width.toFixed(1)} m</text>
    <line x1="${x-28}" y1="${y}" x2="${x-28}" y2="${y+d}" class="plan-dim"/>
    <text x="${x-70}" y="${cy}" class="plan-dim-text">${p.depth.toFixed(1)} m</text>
    <text x="${x+12}" y="${y+24}" class="plan-text">${escapeAnnotation(buildName.value||"Address Build")}</text>
    <text x="${x+12}" y="${y+46}" class="plan-dim-text">Floors: ${p.floors} · Roof: ${p.roof}</text>`;
}

function isoPoint(x,y,z,cx,cy,scale){
  return {
    x:cx+(x-y)*scale,
    y:cy+(x+y)*scale*.48-z*scale
  };
}

function poly(ctx,pts,fill,stroke){
  ctx.beginPath();ctx.moveTo(pts[0].x,pts[0].y);
  pts.slice(1).forEach(p=>ctx.lineTo(p.x,p.y));
  ctx.closePath();ctx.fillStyle=fill;ctx.fill();
  ctx.strokeStyle=stroke;ctx.lineWidth=1.2;ctx.stroke();
}

function renderAddressStructure3D(){
  const canvas=document.getElementById("structure3d");
  if(!canvas)return;
  const rect=canvas.getBoundingClientRect();
  canvas.width=Math.max(700,Math.round(rect.width*1.5));
  canvas.height=Math.max(500,Math.round(rect.height*1.5));
  const ctx=canvas.getContext("2d");
  const p=buildParams();
  const totalH=p.floors*p.floorHeight;
  const scale=Math.min(canvas.width/(p.width+p.depth+12),canvas.height/(totalH+p.width+p.depth+18))*0.72;
  const cx=canvas.width*.5,cy=canvas.height*.72;

  ctx.fillStyle="#06110f";ctx.fillRect(0,0,canvas.width,canvas.height);

  // ground grid
  ctx.strokeStyle="rgba(83,255,208,.12)";ctx.lineWidth=1;
  for(let i=-20;i<=20;i++){
    let a=isoPoint(i,-20,0,cx,cy,scale),b=isoPoint(i,20,0,cx,cy,scale);
    ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
    a=isoPoint(-20,i,0,cx,cy,scale);b=isoPoint(20,i,0,cx,cy,scale);
    ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
  }

  const x0=-p.width/2,x1=p.width/2,y0=-p.depth/2,y1=p.depth/2,z0=0,z1=totalH;
  const A=isoPoint(x0,y0,z0,cx,cy,scale),B=isoPoint(x1,y0,z0,cx,cy,scale),C=isoPoint(x1,y1,z0,cx,cy,scale),D=isoPoint(x0,y1,z0,cx,cy,scale);
  const At=isoPoint(x0,y0,z1,cx,cy,scale),Bt=isoPoint(x1,y0,z1,cx,cy,scale),Ct=isoPoint(x1,y1,z1,cx,cy,scale),Dt=isoPoint(x0,y1,z1,cx,cy,scale);

  poly(ctx,[A,B,Bt,At],"rgba(32,90,75,.85)","#53ffd0");
  poly(ctx,[B,C,Ct,Bt],"rgba(22,62,54,.95)","#53ffd0");
  poly(ctx,[At,Bt,Ct,Dt],"rgba(18,50,44,.95)","#53ffd0");

  // floor bands
  ctx.strokeStyle="#91d8c8";
  for(let f=1;f<p.floors;f++){
    const z=f*p.floorHeight;
    const q1=isoPoint(x0,y0,z,cx,cy,scale),q2=isoPoint(x1,y0,z,cx,cy,scale),q3=isoPoint(x1,y1,z,cx,cy,scale);
    ctx.beginPath();ctx.moveTo(q1.x,q1.y);ctx.lineTo(q2.x,q2.y);ctx.lineTo(q3.x,q3.y);ctx.stroke();
  }

  // simple windows
  ctx.fillStyle="rgba(125,187,255,.7)";
  for(let f=0;f<p.floors;f++){
    const z=f*p.floorHeight+p.floorHeight*.55;
    for(let i=1;i<=3;i++){
      const x=x0+(p.width*i/4);
      const q=isoPoint(x,y0,z,cx,cy,scale);
      ctx.fillRect(q.x-5,q.y-5,10,9);
    }
  }

  // roof
  if(p.roof==="gable"){
    const ridge1=isoPoint(x0,0,z1+p.depth*.28,cx,cy,scale);
    const ridge2=isoPoint(x1,0,z1+p.depth*.28,cx,cy,scale);
    poly(ctx,[At,Bt,ridge2,ridge1],"rgba(40,75,65,.95)","#53ffd0");
    poly(ctx,[Dt,Ct,ridge2,ridge1],"rgba(30,62,55,.95)","#53ffd0");
  }else if(p.roof==="hip"){
    const peak=isoPoint(0,0,z1+Math.min(p.width,p.depth)*.28,cx,cy,scale);
    poly(ctx,[At,Bt,peak],"rgba(40,75,65,.95)","#53ffd0");
    poly(ctx,[Bt,Ct,peak],"rgba(30,62,55,.95)","#53ffd0");
    poly(ctx,[Ct,Dt,peak],"rgba(36,68,60,.95)","#53ffd0");
    poly(ctx,[Dt,At,peak],"rgba(26,58,52,.95)","#53ffd0");
  }

  ctx.fillStyle="#d7fff5";ctx.font="18px Consolas";
  ctx.fillText(buildName.value||"Sentinel Address Build",24,32);
  ctx.fillStyle="#78a89d";ctx.font="14px Consolas";
  ctx.fillText(`${p.width}m × ${p.depth}m · ${p.floors} floors · ${(totalH).toFixed(1)}m wall height · ${p.roof} roof`,24,56);
  if(currentBuildLocation) ctx.fillText(currentBuildLocation.address,24,80);
}

async function saveAddressBuildProject(){
  if(!currentBuildLocation){
    alert("Find an address first.");
    return;
  }
  const p=buildParams();
  await api("/kelowna/api/building-projects",{method:"POST",body:JSON.stringify({
    name:buildName.value||"Sentinel Address Build",
    address:currentBuildLocation.address,
    lat:currentBuildLocation.lat,lon:currentBuildLocation.lon,
    width_m:p.width,depth_m:p.depth,floors:p.floors,
    floor_height_m:p.floorHeight,roof_style:p.roof,rotation_deg:p.rotation,
    notes:buildNotes.value,
    footprint:[
      [-p.width/2,-p.depth/2],[p.width/2,-p.depth/2],
      [p.width/2,p.depth/2],[-p.width/2,p.depth/2]
    ]
  })});
  await loadBuildProjects();
}

async function loadBuildProjects(){
  try{buildProjects=await api("/kelowna/api/building-projects");renderBuildProjects();}catch(e){}
}
function renderBuildProjects(){
  if(!buildProjectList)return;
  buildProjectList.innerHTML=buildProjects.map(p=>`
    <div class="build-row"><strong>${escapeAnnotation(p.name)}</strong>
    <div class="meta">${escapeAnnotation(p.address)}</div>
    <div>${p.width_m}m × ${p.depth_m}m · ${p.floors} floors</div>
    <button data-loadbuild="${p.id}">Load</button>
    <button data-delbuild="${p.id}">Delete</button></div>`).join("")||'<div class="muted">No saved address builds.</div>';

  buildProjectList.querySelectorAll("[data-loadbuild]").forEach(b=>b.addEventListener("click",()=>{
    const p=buildProjects.find(x=>x.id===Number(b.dataset.loadbuild));if(!p)return;
    currentBuildLocation={address:p.address,lat:Number(p.lat),lon:Number(p.lon)};
    buildAddress.value=p.address;buildName.value=p.name;buildWidth.value=p.width_m;buildDepth.value=p.depth_m;
    buildFloors.value=p.floors;buildFloorHeight.value=p.floor_height_m;buildRoof.value=p.roof_style;
    buildRotation.value=p.rotation_deg;buildNotes.value=p.notes||"";
    geocodeResult.textContent=`${p.address} · ${Number(p.lat).toFixed(6)}, ${Number(p.lon).toFixed(6)}`;
    document.querySelector('.tab[data-mode="addressbuild"]')?.click();
    setTimeout(()=>{generateAddressBlueprint();renderAddressStructure3D();},50);
  }));
  buildProjectList.querySelectorAll("[data-delbuild]").forEach(b=>b.addEventListener("click",async()=>{
    if(confirm("Delete this address build project?")){
      await api(`/kelowna/api/building-projects/${b.dataset.delbuild}`,{method:"DELETE"});
      await loadBuildProjects();
    }
  }));
}

findAddress?.addEventListener("click",geocodeBuildAddress);
generateBlueprint?.addEventListener("click",generateAddressBlueprint);
renderStructure?.addEventListener("click",renderAddressStructure3D);
saveBuildProject?.addEventListener("click",saveAddressBuildProject);
[buildWidth,buildDepth,buildFloors,buildFloorHeight,buildRotation,buildRoof].forEach(el=>{
  el?.addEventListener("input",()=>{generateAddressBlueprint();renderAddressStructure3D();});
});
loadBuildProjects();

let cadZoom=1,cadPanX=0,cadPanY=0,cadDrag=false,cadLX=0,cadLY=0;
function applyCadView(){const s=document.getElementById("canvas");if(!s)return;const w=1200/cadZoom,h=800/cadZoom;s.setAttribute("viewBox",`${(1200-w)/2-cadPanX} ${(800-h)/2-cadPanY} ${w} ${h}`);cadZoomLabel.textContent=`${Math.round(cadZoom*100)}%`;}
cadZoomIn?.addEventListener("click",()=>{cadZoom=Math.min(8,cadZoom*1.25);applyCadView()});
cadZoomOut?.addEventListener("click",()=>{cadZoom=Math.max(.35,cadZoom/1.25);applyCadView()});
cadZoomExtents?.addEventListener("click",()=>{cadZoom=1;cadPanX=0;cadPanY=0;applyCadView()});
canvas?.addEventListener("wheel",e=>{e.preventDefault();cadZoom=e.deltaY<0?Math.min(8,cadZoom*1.12):Math.max(.35,cadZoom/1.12);applyCadView()},{passive:false});
canvas?.addEventListener("mousedown",e=>{if(e.shiftKey||e.button===1){cadDrag=true;cadLX=e.clientX;cadLY=e.clientY}});
window.addEventListener("mousemove",e=>{if(!cadDrag)return;cadPanX+=(e.clientX-cadLX)/cadZoom;cadPanY+=(e.clientY-cadLY)/cadZoom;cadLX=e.clientX;cadLY=e.clientY;applyCadView()});
window.addEventListener("mouseup",()=>cadDrag=false);applyCadView();

function loadMcCurdyPreset(){
 buildAddress.value="130 McCurdy Rd, Kelowna, BC";buildName.value="130 McCurdy Rd Concept Build";
 buildFloors.value=4;buildFloorHeight.value=3;buildRoof.value="flat";buildWidth.value=28;buildDepth.value=20;
 buildNotes.value="Public records describe a four-storey development here. Width/depth are conceptual placeholders, not surveyed dimensions.";
 geocodeBuildAddress();document.querySelector('.tab[data-mode="addressbuild"]')?.click();
 setTimeout(()=>{generateAddressBlueprint();renderAddressStructure3D()},300);
}
loadMcCurdy?.addEventListener("click",loadMcCurdyPreset);

const pick=a=>a[Math.floor(Math.random()*a.length)], rr=(a,b)=>a+Math.random()*(b-a);
function applyWorldLevel(){const p={beginner:["small","Low",40,15,3],medium:["medium","Medium",120,30,8],advanced:["large","High",350,60,16]}[worldLevel.value];if(p){worldSize.value=p[0];worldDensity.value=p[1];worldPopulation.value=p[2];worldWildlife.value=p[3];worldNetworkNodes.value=p[4];}worldPresetInfo.textContent=worldLevel.value+" preset loaded";}
worldLevel?.addEventListener("change",applyWorldLevel);
function renderGeneratedWorld(label="Generated World"){
 worldObjects.innerHTML="";let density={Low:12,Medium:24,High:40,"Very High":60}[worldDensity.value]||24;
 for(let i=0;i<6;i++){let r=document.createElement("div");r.className="world-road";if(i%2){r.style.cssText=`left:0;right:0;top:${15+i*12}%;height:7px`}else{r.style.cssText=`top:0;bottom:0;left:${12+i*13}%;width:7px`}worldObjects.appendChild(r)}
 for(let i=0;i<density;i++){let e=document.createElement("button");e.className="world-object";e.style.left=`${rr(4,91)}%`;e.style.top=`${rr(7,88)}%`;e.textContent=pick(["⌂","▦","🏢","🏭","🏪"])+" "+worldBuildings.value;worldObjects.appendChild(e)}
 for(let i=0;i<Number(worldNetworkNodes.value||0);i++){let e=document.createElement("div");e.className="world-node";e.style.left=`${rr(5,92)}%`;e.style.top=`${rr(8,90)}%`;e.textContent=i%3===0?"☎ PBX":i%3===1?"⌁ AP":"◆ NODE";worldObjects.appendChild(e)}
 worldSummary.textContent=`${label} · ${worldType.value} · ${worldSize.value} · ${worldDensity.value}`;
}
generateWorld?.addEventListener("click",()=>renderGeneratedWorld());
randomizeWorld?.addEventListener("click",()=>{worldType.value=pick(["city","suburb","village","industrial","campus","fantasy","sci-fi","wilderness","mixed"]);worldSize.value=pick(["small","medium","large","huge"]);worldDensity.value=pick(["Low","Medium","High","Very High"]);worldPopulation.value=Math.round(rr(20,900));worldWildlife.value=Math.round(rr(0,150));worldNetworkNodes.value=Math.round(rr(2,25));renderGeneratedWorld("Randomized World")});
worldFromMcCurdy?.addEventListener("click",()=>{worldType.value="mixed";worldSize.value="medium";worldDensity.value="High";worldBuildings.value="Mixed Use";worldPopulation.value=250;worldNetworkNodes.value=12;renderGeneratedWorld("130 McCurdy Parallel District")});
applyWorldLevel();
