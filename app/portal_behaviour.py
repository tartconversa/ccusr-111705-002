"""本地业务页面交互。"""

def detail_fragment(item):
    return "<select id=\"date\"><option>周六</option><option>周日</option></select><button id=\"slots\">核对档期</button><output id=\"slot-text\"></output><button id=\"hold\">模拟临时占位</button><script>let date=document.querySelector('#date');let slots=document.querySelector('#slot-text');let hold=false;date.onchange=()=>{hold=false;slots.textContent='加载中';setTimeout(()=>slots.textContent=date.value+'：'+(date.value==='周六'?'余 4 位':'余 2 位'),50)};document.querySelector('#slots').onclick=()=>{slots.textContent='加载中';setTimeout(()=>slots.textContent=date.value+'：'+(hold?'占位中':date.value==='周六'?'余 4 位':'余 2 位'),50)};document.querySelector('#hold').onclick=()=>{hold=true;slots.textContent=date.value+'：占位中'};</script>"
