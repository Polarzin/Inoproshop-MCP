import assert from 'node:assert/strict';
import test from 'node:test';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import {validateRequest,runEngineering,SERVO_TYPES} from '../engineering.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base={action:'servo',operation:'read',project:path.join(root,'sample.project'),path:'Device/EtherCAT/Drive',index:24730,subindex:0};
const write={...base,operation:'write',data_type:'UDINT',value:'1000',expected_raw_hex:'e8030000',expected_address:'controller-address'};

test('servo operations validate before the IDE is accessed',async()=>{
  for(const operation of ['read','dictionary','startup']) assert.equal(validateRequest({...base,operation}).operation,operation);
  assert.equal(validateRequest(write),write);
  for(const data_type of SERVO_TYPES) assert.equal(validateRequest({...write,data_type}).data_type,data_type);
  const rejected=[
    [{operation:'motion'},/Unknown servo/], [{path:''},/device path/],
    [{index:undefined},/index and subindex/], [{subindex:256},/subindex/],
    [{index:1.5},/index/], [{data_type:'STRING'},/data_type/],
    [{operation:'write',value:1000},/value string/],
    [{...write,expected_raw_hex:'f'},/expected_raw_hex/],
    [{...write,expected_address:''},/expected_address/],
    [{...write,steps:[{op:'save'}]},/engineering steps/],
    [{operation:'dictionary',limit:201},/limit/],
    [{operation:'dictionary',query:3},/query/]
  ];
  for(const [patch,error] of rejected) assert.throws(()=>validateRequest({...base,...patch}),error);
  await assert.rejects(runEngineering({...write,expected_address:undefined},{exe:path.join(root,'never-start.exe'),profile:'unused'}),/expected_address/);
});

test('existing offline requests retain their validation',()=>{
  assert.equal(validateRequest({action:'create_empty',project:base.project}).action,'create_empty');
  assert.throws(()=>validateRequest({action:'batch',project:base.project,steps:[]}),/offline steps/);
  assert.throws(()=>validateRequest({action:'build_c6',project:base.project}),/blank software-controller template/);
});

test('MCP advertises the separate servo tool and rejects incomplete writes without an IDE',async()=>{
  const client=new Client({name:'servo-contract-test',version:'1'});
  const env={...process.env};
  delete env.INOPROSHOP_EXE;
  delete env.INOPROSHOP_PROFILE;
  await client.connect(new StdioClientTransport({command:process.execPath,args:[path.join(root,'server.mjs')],env}));
  try {
    const tools=(await client.listTools()).tools;
    const servo=tools.find(x=>x.name==='codesys_servo');
    assert(servo);
    assert(tools.some(x=>x.name==='codesys_engineering'));
    assert.deepEqual(servo.inputSchema.properties.action.enum,['read','write','dictionary','startup']);
    assert.equal(servo.inputSchema.properties.value.type,'string');
    const args={...write,action:'write'};
    delete args.operation;
    delete args.expected_raw_hex;
    const missing=await client.callTool({name:'codesys_servo',arguments:args});
    assert.equal(missing.isError,true);
    assert.match(missing.content[0].text,/expected_raw_hex/);
    const unconfigured=await client.callTool({name:'codesys_servo',arguments:{action:'read',project:base.project,path:base.path,index:base.index,subindex:0}});
    assert.equal(unconfigured.isError,true);
    assert.match(unconfigured.content[0].text,/INOPROSHOP_EXE/);
  } finally {await client.close();}
});
