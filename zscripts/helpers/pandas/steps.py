from helpers.utilities.paths import org_path

import pandas as pd

# Generating a CSV type log of steps for deploying the system
# Including steps for SharePoint, Teams, and WordPress setup and integration

# Defining the steps
steps = [
    {
        "Priority": 1,
        "Software": "SharePoint",
        "Step": "Create SharePoint sites for departments/project teams",
    },
    {"Priority": 2, "Software": "SharePoint", "Step": "Set up document libraries with permissions"},
    {"Priority": 3, "Software": "SharePoint", "Step": "Upload and organize essential documents"},
    {"Priority": 4, "Software": "SharePoint", "Step": "Implement a tagging and search system"},
    {"Priority": 5, "Software": "SharePoint", "Step": "Set up knowledge bases or wikis"},
    {"Priority": 6, "Software": "Teams", "Step": "Create channels for different topics/projects"},
    {"Priority": 7, "Software": "Teams", "Step": "Integrate SharePoint libraries into Teams"},
    {"Priority": 8, "Software": "Teams", "Step": "Enable meetings and video conferencing"},
    {"Priority": 9, "Software": "Teams", "Step": "Use shared workspaces for collaboration"},
    {"Priority": 10, "Software": "Teams", "Step": "Identify areas for bot assistance"},
    {
        "Priority": 11,
        "Software": "Teams",
        "Step": "Develop/configure bots (GPTs, Copilots, OpenAI)",
    },
    {"Priority": 12, "Software": "Teams", "Step": "Deploy and integrate bots in Teams"},
    {"Priority": 13, "Software": "Teams", "Step": "Conduct training for bot usage"},
    {"Priority": 14, "Software": "Power Automate", "Step": "Analyze workflows for automation"},
    {"Priority": 15, "Software": "Power Automate", "Step": "Create automation flows"},
    {
        "Priority": 16,
        "Software": "Microsoft Graph API",
        "Step": "Plan API integration for enhanced functionalities",
    },
    {
        "Priority": 17,
        "Software": "Microsoft Graph API",
        "Step": "Develop and test integration solutions",
    },
    {"Priority": 18, "Software": "WordPress", "Step": "Plan website layout and design"},
    {"Priority": 19, "Software": "WordPress", "Step": "Develop pages for services and objectives"},
    {"Priority": 20, "Software": "WordPress", "Step": "Create and publish engaging content"},
    {
        "Priority": 21,
        "Software": "WordPress",
        "Step": "Implement interactive elements (blogs, forms)",
    },
    {"Priority": 22, "Software": "WordPress", "Step": "Optimize site for user experience"},
    {"Priority": 23, "Software": "WordPress", "Step": "Perform SEO and technical optimizations"},
    {"Priority": 24, "Software": "WordPress", "Step": "Develop a digital marketing plan"},
    {"Priority": 25, "Software": "WordPress", "Step": "Set up lead generation systems"},
    {"Priority": 26, "Software": "WordPress", "Step": "Develop lead management processes"},
    {
        "Priority": 27,
        "Software": "General",
        "Step": "Implement user group and community creation features",
    },
    {
        "Priority": 28,
        "Software": "General",
        "Step": "Enable users to bring and integrate their own bots",
    },
]

# Converting the steps to a CSV format

# Create a DataFrame
df = pd.DataFrame(steps)

# Save to a CSV file
csv_file = str(org_path("Core", "mnt", "data", "system_deployment_steps.csv"))
df.to_csv(csv_file, index=False)
print("Wrote:", csv_file)
