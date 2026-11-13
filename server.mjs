#!/usr/bin/env node
import {McpServer} from '@modelcontextprotocol/sdk/server/mcp.js';
import {StdioServerTransport} from '@modelcontextprotocol/sdk/server/stdio.js';
import {z} from 'zod';
import {runEngineering,SERVO_TYPES} from './engineering.mjs';
const server=new McpServer({name:'inoproshop-mcp',version:'0.1.0'});
let busy=false;
async function execute(request) {
  if(busy) return {isError:true,content:[{type:'text',text:'IDE session in progress; request not queued'}]};
  busy=true;
  try {
    const result=await runEngineering(request,{exe:process.env.INOPROSHOP_EXE,profile:process.env.INOPROSHOP_PROFILE});
    return {isError:!result.ok,content:[{type:'text',text:JSON.stringify(result)}]};
  } catch(error) {return {isError:true,content:[{type:'text',text:String(error)}]};}
  finally {busy=false;}
}
server.tool('codesys_engineering',
  'Offline IDE only. create_empty creates an empty project container (no controller). build_c6 copies a user-provided blank software-controller template created through the official IDE or documented ScriptEngine configuration. The template is kept unchanged; project must be a new output path. It then adds synthetic virtual axes/ST/task/symbols. batch edits an existing synthetic project using worker_api operations. Saves changes. Never logs into or downloads to a PLC. Close other IDE instances first, or explicitly use isolated=true for a separate user configuration. Failed batches are not retried.',
  {action:z.enum(['create_empty','batch','build_c6']),project:z.string(),isolated:z.boolean().optional(),template:z.string().optional(),
   steps:z.array(z.object({op:z.enum(['tree','list','read','read_lines','patch','write','create','rename','move','delete','compile','save',
     'device','device_parameters','device_parameter_write','device_add','repository_devices','task','task_configure',
     'libraries','library_add','symbols_create','symbols','symbol_access','verify_symbols','generate_code','export_boot']),
     args:z.record(z.unknown()).default({}).describe('Slash paths from tree (Application alias only when unique); no recursive name fallback. create: parent (empty=project root), name, kind=action|pou(FB)|program|function|method|property|dut|folder|gvl|task, optional return_type, dut_type=structure|enumeration|alias|union, base_type, language=ST. read/write: path; write declaration and/or implementation; Property accessors use /Get or /Set child paths from read. rename: path,name. move: path,parent (empty=project root). delete: path,recursive=false; true explicitly includes every descendant. Mutations return readback; optional save=true saves immediately. Failed batches may preserve partial edits; inspect before retry.')})).optional(),
   axis:z.object({type:z.number().int(),id:z.string(),version:z.string()}).optional()},
  execute);
server.tool('codesys_servo',
  'EtherCAT servo parameters through the installed InoProShop 1.9.1.6 native CoE adapter. read uploads one online SDO; write downloads one typed value after checking the prior raw bytes and configured controller address, then reads it back. dictionary reads the installed ESI metadata; startup reads project startup values. Uses the communication path saved in the project. Does not save the project, download the PLC application, retry failed requests, or send additional start, stop, reset, motion, or nonvolatile-storage commands. The selected object itself determines immediate, restart-dependent, or stored effects and side effects according to the drive definition. Client timeout is not cancellation. Close other IDE instances first or explicitly use isolated=true with a separate project copy.',
  {action:z.enum(['read','write','dictionary','startup']),project:z.string(),isolated:z.boolean().optional(),
   path:z.string().min(1).describe('Exact slash-separated device path from the engineering tree'),
   connector_id:z.string().min(1).optional().describe('EtherCAT slave connector ID; default 1'),
   index:z.number().int().min(1).max(65535).optional().describe('Object index as a decimal integer; 0x609A = 24730'),
   subindex:z.number().int().min(0).max(255).optional(),
   data_type:z.enum(SERVO_TYPES).optional(),
   value:z.string().min(1).optional().describe('Typed numeric string for write; keep 64-bit integers as strings'),
   expected_raw_hex:z.string().regex(/^(?:[0-9a-fA-F]{2})+$/).optional().describe('Required for write; exact raw_hex from a successful read'),
   expected_address:z.string().min(1).optional().describe('Required for write; configured controller address returned by read'),
   query:z.string().optional(),offset:z.number().int().min(0).optional(),limit:z.number().int().min(1).max(200).optional()},
  args=>execute({...args,action:'servo',operation:args.action}));
await server.connect(new StdioServerTransport());
