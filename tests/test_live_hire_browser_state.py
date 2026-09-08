import subprocess
from pathlib import Path


def test_new_service_does_not_resume_an_unrelated_cached_order():
    script = Path('apps/web/assets/live-hire.js').read_text()
    function = script.split('function savedJob() {', 1)[1].split('\nasync function waitForReceipt', 1)[0]
    program = '''const assert = require('node:assert/strict');
const location = {search:''};
const STORAGE_KEY='test';
const taskJSON=JSON;
const localStorage={getItem:()=>JSON.stringify({job_id:56741})};
function savedJob() {''' + function + '''
location.search='?skill_id=health_factor&agent_token_id=269228'; assert.equal(savedJob(),null);
location.search='?skill_id=grid_plan&agent_token_id=269224'; assert.equal(savedJob(),null);
location.search='?job_id=56733'; assert.equal(savedJob(),56733);
location.search='?job_id=invalid'; assert.equal(savedJob(),null);
location.search=''; assert.equal(savedJob(),56741);
'''
    subprocess.run(['node', '-e', program], check=True, capture_output=True, text=True)
