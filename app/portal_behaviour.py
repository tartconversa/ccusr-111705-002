"""本地业务页面交互。"""

def detail_fragment(item):
    return "<select id=\"date\"><option>周六</option><option>周日</option></select><button id=\"slots\">核对档期</button><output id=\"slot-text\"></output><button id=\"hold\">模拟临时占位</button><script>let date=document.querySelector('#date');let slots=document.querySelector('#slot-text');let hold=false;date.onchange=()=>{hold=false;slots.textContent='加载中';setTimeout(()=>slots.textContent=date.value+'：'+(date.value==='周六'?'余 4 位':'余 2 位'),50)};document.querySelector('#slots').onclick=()=>{slots.textContent='加载中';setTimeout(()=>slots.textContent=date.value+'：'+(hold?'占位中':date.value==='周六'?'余 4 位':'余 2 位'),50)};document.querySelector('#hold').onclick=()=>{hold=true;slots.textContent=date.value+'：占位中'};</script>"

def source_extension(item):
    return f"""<label>同行人数<select id="party-size"><option value="1">1</option><option value="4">4</option></select></label><output id="hold-preview" data-project="{item['id']}"></output><script>(()=>{{
let party=document.querySelector('#party-size'),preview=document.querySelector('#hold-preview'),date=document.querySelector('#date');
let capacity={{'周六':{4 if item['id']=='robot-art' else 2},'周日':{2 if item['id']=='robot-art' else 1}}};let held=false;
const reset=()=>{{held=false;preview.textContent='';}};date.addEventListener('change',reset);party.addEventListener('change',()=>preview.textContent='');
document.querySelector('#preview').addEventListener('click',()=>{{let selected=date.value,count=Number(party.value),wasHeld=held;preview.textContent='占位核对中';setTimeout(()=>{{preview.textContent=selected+' / '+count+' 人：'+(wasHeld?'临时占位':count>capacity[selected]?'人数超出名额':'等待确认');}},70)}});
document.querySelector('#hold').addEventListener('click',()=>{{held=true;preview.textContent=date.value+'：临时占位';}});
}})();</script>"""
