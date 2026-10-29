#!/usr/bin/env node
import {McpServer} from '@modelcontextprotocol/sdk/server/mcp.js';
import {StdioServerTransport} from '@modelcontextprotocol/sdk/server/stdio.js';
import {z} from 'zod';
import {runEngineering} from './engineering.mjs';
const server=new McpServer({name:'inoproshop-offline-mcp',version:'0.1.0'});
let busy=false;
server.tool('codesys_engineering',
  'Offline IDE only. create_empty creates an empty project container (no controller). build_c6 copies a user-provided blank software-controller template created through the official IDE or documented ScriptEngine configuration. The template is kept unchanged; project must be a new output path. It then adds synthetic virtual axes/ST/task/symbols. batch edits an existing synthetic project using worker_api operations. Saves changes. Never logs into or downloads to a PLC. Close other IDE instances first, or explicitly use isolated=true for a separate user configuration. Failed batches are not retried.',
  {action:z.enum(['create_empty','batch','build_c6']),project:z.string(),isolated:z.boolean().optional(),template:z.string().optional(),
   steps:z.array(z.object({op:z.enum(['tree','list','read','read_lines','patch','write','create','rename','move','delete','compile','save',
     'device','device_parameters','device_parameter_write','device_add','repository_devices','task','task_configure',
     'libraries','library_add','symbols_create','symbols','symbol_access','verify_symbols','generate_code','export_boot']),
     args:z.record(z.unknown()).default({}).describe('Slash paths from tree (Application alias only when unique); no recursive name fallback. create: parent (empty=project root), name, kind=action|pou(FB)|program|function|method|property|dut|folder|gvl|task, optional return_type, dut_type=structure|enumeration|alias|union, base_type, language=ST. read/write: path; write declaration and/or implementation; Property accessors use /Get or /Set child paths from read. rename: path,name. move: path,parent (empty=project root). delete: path,recursive=false; true explicitly includes every descendant. Mutations return readback; optional save=true saves immediately. Failed batches may preserve partial edits; inspect before retry.')})).optional(),
   axis:z.object({type:z.number().int(),id:z.string(),version:z.string()}).optional()},
  async args=>{
    if(busy) return {isError:true,content:[{type:'text',text:'Engineering batch in progress; request not queued'}]};
    busy=true;
    try {
      const result=await runEngineering(args,{exe:process.env.INOPROSHOP_EXE,profile:process.env.INOPROSHOP_PROFILE});
      return {isError:!result.ok,content:[{type:'text',text:JSON.stringify(result)}]};
    } catch(error) {return {isError:true,content:[{type:'text',text:String(error)}]};}
    finally {busy=false;}
  });
await server.connect(new StdioServerTransport());
