import asyncio
import os
from harborapi import HarborAsyncClient
from harborapi.models import Project, ImmutableRule, RetentionPolicy
from harborapi.exceptions import NotFound

client = HarborAsyncClient(
    url=f"https://{os.environ['HARBOR_URL']}/api/v2.0/",
    username=os.environ["HARBOR_USERNAME"],
    secret=os.environ["HARBOR_PASSWORD"]
)
TERMINAL_STATES = {"Success", "Error", "Stopped"}

async def enable_immutable_tag_rules(project_id,enabled=True):
    # Create a new immutable tag rule
    rule_immutable = ImmutableRule(
        action="immutable",
        scope_selectors={
            "repository": [{
                "decoration": "repoMatches",
                "kind": "doublestar",
                "pattern": "**"
            }]
        },
        tag_selectors=[{
            "decoration": "matches",
            "kind": "doublestar",
            "pattern": "**"
        }],
        template="immutable_template"
    )

    # Check if immutability rules exist
    try:
        immutability_rules = await client.get_project_immutable_tag_rules(project_id)
        if immutability_rules:
            # print(f"Immutability rules of project {project_id}:")
            for rule in immutability_rules:
                update_rule = ImmutableRule(
                    id=rule.id,
                    action="immutable",
                    scope_selectors=rule.scope_selectors,
                    tag_selectors=rule.tag_selectors,
                    template=rule.template,
                    disabled=enabled  # Disable existing rule
                )
                await client.update_project_immutable_tag_rule(project_id, rule.id, update_rule)
                print(f"disabled immutable tag for {project_id} with rule: {rule.id}") if enabled else print(f"enabled immutable tag for {project_id} with rule: {rule.id}")
        else:
            await client.create_project_immutable_tag_rule(project_id, rule_immutable)
            print(f"Immutability rule created for project {project_id}.")
    except NotFound:
        print("No immutability rules found.")
    return "update immutability rules successfully."

async def get_projects():
    projects = list[Project]
    projects = await client.get_projects()
    projects_id_list = []
    for project in projects:
        # Check if retention policy exists
        try:
            retention_id = project.metadata.retention_id
            # print(retention)
            has_retention = retention_id if retention_id else "No"
        except NotFound:
            has_retention = "No"
        # Check if immutability rules exist
        try:
            immutability_rules = await client.get_project_immutable_tag_rules(project.name)
            has_immutability = immutability_rules[0].id if immutability_rules else "No"
        except NotFound:
            has_immutability = "No"
        # print(f"{project_name:<30} {project_id:<10} {has_retention:<10} {has_immutability}")
        prj ={
            "project_id": project.project_id,
            "name": project.name,
            "retention_id": (int)(project.metadata.retention_id) if project.metadata.retention_id else "No",
            "immutability_id": immutability_rules[0].id if immutability_rules else "No"
        }
        projects_id_list.append(prj)
    return projects_id_list

async def get_project_retention_id(project_id):
    # Get retention policy by project ID
    try:
        retention = await client.get_project_retention_id(project_id)
        return retention
    except NotFound:
        print(f"Project {project_id} not found retention.")
        return None

#Define retention policy
async def create_new_policy(project_id):
    retention_policy = RetentionPolicy(
        algorithm="or",
        scope={
            "level": "project",
            "ref": project_id
        },
        trigger={
            "kind": "Schedule",
            "settings": {
                "cron": "",
            }
        },
        rules=[
        {
            "action": "retain",
            "params": {
            "latestPushedK": 3
            },
            "scope_selectors": {
            "repository": [
                {
                "decoration": "repoMatches",
                "kind": "doublestar",
                "pattern": "**"
                }
            ]
            },
            "tag_selectors": [
            {
                "decoration": "matches",
                "extras": "{\"untagged\":true}",
                "kind": "doublestar",
                "pattern": "t-*"
            }
            ],
            "template": "latestPushedK"
        },
        {
            "action": "retain",
            "params": {
            "latestPushedK": 10
            },
            "scope_selectors": {
            "repository": [
                {
                "decoration": "repoMatches",
                "kind": "doublestar",
                "pattern": "**"
                }
            ]
            },
            "tag_selectors": [
            {
                "decoration": "matches",
                "extras": "{\"untagged\":true}",
                "kind": "doublestar",
                "pattern": "m-*"
            }
            ],
            "template": "latestPushedK"
        },
        {
            "action": "retain",
            "params": {
            "latestPushedK": 10
            },
            "scope_selectors": {
            "repository": [
                {
                "decoration": "repoMatches",
                "kind": "doublestar",
                "pattern": "**"
                }
            ]
            },
            "tag_selectors": [
            {
                "decoration": "matches",
                "extras": "{\"untagged\":true}",
                "kind": "doublestar",
                "pattern": "r-*"
            }
            ],
            "template": "latestPushedK"
        }
        ]
    )
    # check if retention policy exists
    try:
        retention = await client.get_project_retention_id(project_id)
        if retention:
            print(f"Retention policy already exists for project {project_id}.")
            return
    except NotFound:
        print(f"No retention policy found for project {project_id}.")
        await client.create_retention_policy(retention_policy)
        print(f"Retention policy created for project {project_id}.")
        pass  # No retention policy found, proceed to create a new one
    return "create retention policy successfully."

async def start_retention(retention_id,dry_run=True):
    # Start retention policy for a project
    print(f"Retention policy started for retention_id {retention_id}.")

    #Start retention execution
    await client.start_retention_execution(retention_id, dry_run=dry_run)

    #Get the newest execution
    print("⏳ Waiting for new execution to appear...")
    execution_id = None
    for _ in range(10):
        executions  = await client.get_retention_executions(retention_id, page=1, page_size=100)
        if executions:
            execution_id = executions[0].id
            print(f"🔁 Found execution ID: {execution_id}")
            break
        await asyncio.sleep(1)
    if not execution_id:
        print("❌ Could not find any execution.")
        return

    while True:
        executions = await client.get_retention_executions(retention_id, page=1, page_size=100)
        exec_match = next((e for e in executions if e.id == execution_id), None)
        if not exec_match:
            print("⚠️ Execution ID no longer found. Assuming finished.")
            break
        status = exec_match.status
        print(f"🕒 Execution {execution_id} status: {status}")
        if status in TERMINAL_STATES:
            print(f"✅ Execution {execution_id} completed with status: {status}")
            break
        await asyncio.sleep(5)
    

async def main() -> None:
    # Fetch all projects
    projects = await get_projects()
    
    print("🔍 Fetching all projects...")
    print(f"Total Projects: {len(projects)}")
    # print(projects)

    # Define projects not run retention policy
    remove_projects_name = {'base','catalog-mirror','images-mirror','dgx','helm-chart','ht-devops','ht-platforms','team-os','component-ocp','anht','aqua-security','attt-efin','externals','library','glamor-bidv','netops','quanglv2','sre','tools','vhgsdv','vhud','bidv-omni','ansp','bidv-uat','aiomni','project-dung-test','cndl-prod','cndl','devops','drop'}

    # Projects run retention policy
    print("🔍 filtering project...")
    filtered_projects = [p for p in projects if p['name'] not in remove_projects_name]

    print(f"Filtered Projects: {len(filtered_projects)}")
    # print(filtered_projects)

    for project in filtered_projects:
        await enable_immutable_tag_rules(project['project_id'],True)
        await create_new_policy(project['project_id'])
        await start_retention(project['retention_id'],True) if project['retention_id'] != "No" else print(f"Project {project['project_id']} has no retention policy.")
        await enable_immutable_tag_rules(project['project_id'],False)

asyncio.run(main())
