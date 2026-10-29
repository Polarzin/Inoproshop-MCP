const en = {
  skip:'Skip to content',navFeatures:'Functions',navExample:'Flying shear',navStart:'Getting started',
  title:'An MCP interface<br>for InoProShop',intro:'Use the public ScriptEngine API from an MCP client to create and edit projects, read and write Structured Text, run native builds, save projects, and export boot applications.',introNote:'A small tool for PLC engineering operations, with a three-axis flying shear example.',ctaStart:'Read the guide',ctaDemo:'Explore the example',caption:'Three-axis flying shear · Recorded software PLC feedback',fullSize:'Full-size GIF ↗',pause:'Pause GIF',play:'Play GIF',
  featuresTitle:'Supported engineering operations',featuresNote:'Executed through InoProShop’s native engineering API.',feature1Title:'Create and edit',feature1:'Create empty project containers, inspect project structure, and read or modify ST programs and project objects.',feature2Title:'Build and save',feature2:'Run the native compiler and retrieve diagnostics. Save and reopen projects to check changes.',feature3Title:'Export boot applications',feature3:'Export native boot applications for software controllers, for deployment through the official workflow.',
  exampleTitle:'Example: three-axis flying shear',exampleGuide:'Build instructions ↗',exampleIntro:'Starting from a user-prepared blank software-controller template, MCP adds three virtual axes, writes the flying shear ST program, and configures a 10 ms task and 48 interface fields. The project runs on a software PLC; a companion 3D scene displays its feedback.',
  step1Title:'Prepare a template',step1:'Create a blank software-controller project using the official IDE or public API.',step1By:'Prepared by the user',step2Title:'Build the project',step2:'Add virtual axes, the ST program, tasks, and interface fields.',step2By:'MCP engineering operations',step3Title:'Compile and export',step3:'Run the native compiler, check symbols, and export the boot application.',step3By:'MCP engineering operations',step4Title:'Run and observe',step4:'Deploy to a software PLC through the official workflow and connect the 3D scene.',step4By:'User deployment · Companion viewer',
  hardwareTitle:'Hardware use',hardware:'Earlier engineering tooling was used on our own hardware platform to verify project read/write, compilation, and download operations. The three-axis flying shear example in this public version was verified on a software PLC.',
  startTitle:'Getting started',startNote:'Prepare your local environment, then connect an MCP client.',start1Title:'Prepare the environment',start1:'Windows, Node.js ≥ 18, and compatible InoProShop with ScriptEngine. Building the flying shear example requires matching software-controller device descriptions and motion components.',start2Title:'Configure your client',start2:'Install the dependencies and register server.mjs in a stdio MCP client, using the path to your local IDE.',start3Title:'Use engineering operations',start3:'Create an empty project or read and edit existing ST. Prepare a blank controller template before building the flying shear example.',configTitle:'Example MCP client configuration',copy:'Copy',copied:'Copied',copyFailed:'Select the configuration and copy manually.',configNote:'Replace the example paths with absolute paths on your machine.',guideLink:'Installation and usage guide',readmeLink:'Read the README ↗',footer:'Independently developed. Original code is MIT licensed; obtain vendor software and components from official sources.',noticeLink:'Third-party notices',downloadReadme:'Download README',back:'← Back to overview'
};
const zh = Object.fromEntries([...document.querySelectorAll('[data-i18n]')].map(el=>[el.dataset.i18n,el.innerHTML]));
Object.assign(zh,{pause:'暂停动图',play:'播放动图',copied:'已复制',copyFailed:'请选中配置内容后手动复制。'});
let lang='zh';let paused=false;let stillFrame=null;
function setLanguage(next){
  lang=next==='en'?'en':'zh';const strings=lang==='en'?en:zh;
  document.documentElement.lang=lang==='en'?'en':'zh-CN';
  for(const el of document.querySelectorAll('[data-i18n]')){const value=strings[el.dataset.i18n];if(value!==undefined)el.innerHTML=value;}
  for(const el of document.querySelectorAll('[data-lang]'))el.setAttribute('aria-pressed',String(el.dataset.lang===lang));
  const nav=document.querySelector('[data-nav]');if(nav)nav.setAttribute('aria-label',lang==='en'?'Main navigation':'主导航');
  const brand=document.querySelector('a.brand');if(brand)brand.setAttribute('aria-label',lang==='en'?'InoProShop MCP home':'InoProShop MCP 首页');
  const img=document.getElementById('demo');if(img)img.alt=lang==='en'?'Recorded software PLC feedback for the original three-axis flying shear example':'原创三轴飞剪案例的软件 PLC 运行反馈录像';
  for(const link of document.querySelectorAll('[data-doc]'))link.href=`${link.dataset.doc}.html${lang==='en'?'?lang=en':''}`;
  for(const link of document.querySelectorAll('a[href^="index.html"]'))link.href=`index.html${lang==='en'?'?lang=en':''}`;
  const download=document.querySelector('[download]');if(download)download.href=lang==='en'?'../../README.en.md':'../../README.md';
  const u=new URL(location.href);if(lang==='en')u.searchParams.set('lang','en');else u.searchParams.delete('lang');history.replaceState({},'',u);
  const toggle=document.getElementById('media-toggle');if(toggle)toggle.textContent=strings[paused?'play':'pause'];
  const copyStatus=document.getElementById('copy-status');if(copyStatus)copyStatus.textContent='';
  document.title=lang==='en'?'InoProShop MCP · Engineering interface':'InoProShop MCP · 工程接口';
  document.querySelector('meta[name="description"]')?.setAttribute('content',lang==='en'?en.intro:zh.intro||'InoProShop MCP 工程接口与使用说明');
}
document.querySelectorAll('[data-lang]').forEach(el=>el.addEventListener('click',()=>setLanguage(el.dataset.lang)));
setLanguage(new URLSearchParams(location.search).get('lang'));
const demo=document.getElementById('demo');
function pauseDemo(){if(!demo||!demo.complete||!demo.naturalWidth)return;const c=document.createElement('canvas');c.width=demo.naturalWidth;c.height=demo.naturalHeight;c.getContext('2d').drawImage(demo,0,0);stillFrame=c.toDataURL('image/png');demo.src=stillFrame;paused=true;updateMediaButton();}
function updateMediaButton(){const b=document.getElementById('media-toggle');if(!b)return;b.textContent=(lang==='en'?en:zh)[paused?'play':'pause'];b.setAttribute('aria-pressed',String(paused));}
document.getElementById('media-toggle')?.addEventListener('click',()=>{if(paused){demo.src='../assets/flying-shear.gif';paused=false;updateMediaButton();}else pauseDemo();});
if(demo&&matchMedia('(prefers-reduced-motion: reduce)').matches){if(demo.complete)pauseDemo();else demo.addEventListener('load',pauseDemo,{once:true});}
document.getElementById('copy-config')?.addEventListener('click',async()=>{
  const text=document.getElementById('config-code').textContent;const b=document.getElementById('copy-config');const strings=lang==='en'?en:zh;
  try{await navigator.clipboard.writeText(text);b.textContent=strings.copied;document.getElementById('copy-status').textContent=strings.copied;setTimeout(()=>{b.textContent=(lang==='en'?en:zh).copy},2000);}
  catch{const selection=getSelection();const range=document.createRange();range.selectNodeContents(document.getElementById('config-code'));selection.removeAllRanges();selection.addRange(range);document.getElementById('copy-status').textContent=strings.copyFailed;}
});
