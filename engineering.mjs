import {promises as fs} from 'node:fs';
import path from 'node:path';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));

export function validateRequest(request) {
  if(!request || !['create_empty','batch','build_c6'].includes(request.action)) throw new Error('Unknown offline action');
  if(!path.isAbsolute(request.project) || !request.project.toLowerCase().endsWith('.project'))
    throw new Error('An absolute .project path is required');
  if(request.template && (!path.isAbsolute(request.template) || !request.template.toLowerCase().endsWith('.project')))
    throw new Error('An absolute local .project template is required');
  if('adapter' in request || 'controller' in request)
    throw new Error('Internal controller adapters are not included; create a blank software-controller template through the official IDE or documented ScriptEngine configuration');
  if(request.template && request.action!=='build_c6')
    throw new Error('template is supported only for build_c6; create_empty always creates a new empty container');
  if(request.action==='build_c6' && !request.template)
    throw new Error('Provide a blank software-controller template created through the official IDE or documented ScriptEngine configuration');
  if(request.template && path.resolve(request.template).toLowerCase()===path.resolve(request.project).toLowerCase())
    throw new Error('Template and output must be different paths');
  if(request.action==='batch' && (!Array.isArray(request.steps) || !request.steps.length || request.steps.length>200))
    throw new Error('Provide 1..200 offline steps');
  return request;
}

export async function runEngineering(request, {exe, profile, timeoutMs=600000}={}) {
  validateRequest(request);
  if(!exe || !path.isAbsolute(exe) || !profile) throw new Error('Set INOPROSHOP_EXE and INOPROSHOP_PROFILE');
  await fs.access(exe);
  if(request.template && !(await fs.stat(request.template)).isFile())
    throw new Error('Template must be an existing local project file');
  if(request.isolated !== undefined && typeof request.isolated !== 'boolean') throw new Error('isolated must be boolean');
  if(process.platform==='win32' && !request.isolated) {
    const {stdout}=await promisify(execFile)('powershell.exe',['-NoProfile','-Command',
      '@(Get-Process InoProShop,CODESYS -ErrorAction SilentlyContinue).Count'],{windowsHide:true,timeout:15000});
    if(stdout.trim()!=='0') throw new Error('Another IDE is open; close it yourself before running an offline batch');
  }
  await fs.mkdir(path.join(root,'var'),{recursive:true});
  // A failed/timeout batch is never retried. The lock persists if IDE exit is unknown.
  const lockPath=path.join(root,'var/engineering.lock');
  const lock=await fs.open(lockPath,'wx').catch(()=>{throw new Error('Engineering session locked; inspect the previous IDE and result before removing var/engineering.lock');});
  let child, exited=false;
  try {
    const run=await fs.mkdtemp(path.join(root,'var/engineering-'));
    await lock.writeFile(JSON.stringify({pid:process.pid,run,project:request.project}));
    await fs.writeFile(path.join(run,'request.json'),JSON.stringify({...request,root}));
    const env={...process.env, __COMPAT_LAYER:'RunAsInvoker'};
    if(request.isolated) {
      for(const [key,folder] of Object.entries({USERPROFILE:'profile',APPDATA:'profile/Roaming',LOCALAPPDATA:'profile/Local',TEMP:'tmp',TMP:'tmp'})) {
        env[key]=path.join(run,folder);await fs.mkdir(env[key],{recursive:true});
      }
    }
    const header='# -*- coding: utf-8 -*-\nREQUEST_PATH = u'+JSON.stringify(path.join(run,'request.json'))+'\n';
    await fs.writeFile(path.join(run,'script.py'),header+await fs.readFile(path.join(root,'worker.py'),'utf8'));
    const completion=new Promise((resolve,reject)=>{
      child=spawn(exe,[`--profile=${profile}`,`--runscript=${path.join(run,'script.py')}`],{stdio:'ignore',windowsHide:true,env});
      child.once('error',error=>{exited=true;reject(error);});
      child.once('exit',(code,signal)=>{exited=true;resolve({code,signal});});
    });
    if(child.pid) await fs.writeFile(path.join(run,'owner.json'),JSON.stringify({pid:child.pid}));
    let timer;
    try {
      await Promise.race([completion,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(`IDE result unknown; no automatic retry or termination. Inspect ${run}`)),timeoutMs);})]);
    } finally {clearTimeout(timer);}
    const result=JSON.parse(await fs.readFile(path.join(run,'result.json'),'utf8'));
    if(result.ide_pid!==child.pid) throw new Error('IDE process ownership mismatch; inspect result without retry');
    return {...result,run};
  } finally {
    await lock.close();
    if(!child || exited) await fs.unlink(lockPath);
  }
}
