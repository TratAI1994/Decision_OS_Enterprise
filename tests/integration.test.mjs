import test from 'node:test';import assert from 'node:assert/strict';import{readFileSync}from'node:fs';
const source=readFileSync(new URL('../src/main.jsx',import.meta.url),'utf8');
test('light enterprise skin included after base skin',()=>assert.ok(source.indexOf("./enterprise-light.css")>source.indexOf("./styles.css")));
test('readiness workbench actually mounted',()=>assert.match(source,/view==='assessment'\s*&&\s*<TransformationAssessment\/>/));
test('portfolio functionality retained',()=>assert.match(source,/view==='portfolio'\s*&&\s*<PortfolioStudio\/>/));
test('ledger backend view remains present',()=>assert.match(source,/<DecisionLedger/));
test('trust boundary: browser does not embed collector secret',()=>{assert.doesNotMatch(source,/DECISION_OS_COLLECTOR_KEY_HEX/);assert.doesNotMatch(source,/secret[_-]?key\s*=/i)});
