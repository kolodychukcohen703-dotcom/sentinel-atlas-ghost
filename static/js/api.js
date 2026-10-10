export async function postJSON(url,data={}){const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});return await res.json();}
export async function getJSON(url){const res=await fetch(url);return await res.json();}
