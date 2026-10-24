#!/usr/bin/env node
/** Local release gate, deliberately no self-certification or production mutation. */
import {spawnSync} from 'node:child_process';
import {writeFileSync, existsSync} from 'node:fs';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'..','frontend');
const results=[];
function command(name,args){const p=spawnSync(process.platform==='win32'?'npm.cmd':'npm',args,{cwd:root,encoding:'utf8',timeout:120000});results.push({gate:name,status:p.status===0?'PASS':'FAIL',exit_code:p.status,detail:(p.stderr||p.stdout||'').slice(-1200)});process.stdout.write(`${name}: ${p.status===0?'PASS':'FAIL'}\n`);return p.status===0}
const test=command('node_unit_tests',['test']);
const nodeModules=existsSync(resolve(root,'node_modules','.bin','vite')) || existsSync(resolve(root,'node_modules','vite'));
const build=nodeModules?command('vite_production_build',['run','build']):(results.push({gate:'vite_production_build',status:'BLOCKED',detail:'Node dependencies are not installed; run npm install followed by npm run build in your Windows project'}),process.stdout.write('vite_production_build: BLOCKED (dependencies missing)\n'),false);
results.push({gate:'live_postgresql_negative_controls',status:'NOT_TESTED',detail:'Requires R9.9-LV execution in an isolated PostgreSQL test environment'});
results.push({gate:'real_jenkins_to_deployment_provenance',status:'NOT_TESTED',detail:'No Jenkins deployment source evidence connected by this release'});
results.push({gate:'finance_erp_reconciliation',status:'NOT_TESTED',detail:'Requires authorized GL/ERP connector and independent validation'});
results.push({gate:'browser_accessibility_and_auth',status:'NOT_TESTED',detail:'Requires actual browser and supported user identity tests'});
const report={schema:'decision-os-release-check-v1',results,production_certified:false,build_ready:test&&build};
writeFileSync(resolve(root,'release-gate-report.json'),JSON.stringify(report,null,2)+'\n');
process.stdout.write('Report: frontend/release-gate-report.json\n');
if(!test||!build)process.exitCode=1;
