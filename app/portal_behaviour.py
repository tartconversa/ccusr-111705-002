"""本地业务页面交互。"""

def detail_fragment(item):
    return '<select id="date"><option>周六</option><option>周日</option></select><button id="slots">核对档期</button><output id="slot-text"></output><script>document.querySelector(\'#slots\').onclick=()=>{let day=document.querySelector(\'#date\').value;document.querySelector(\'#slot-text\').textContent=\'加载中\';setTimeout(()=>document.querySelector(\'#slot-text\').textContent=day+\'：体验档期\',50)};document.querySelector(\'#date\').onchange=()=>document.querySelector(\'#slot-text\').textContent=\'\';</script>'
