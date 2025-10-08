# Quick Installation Guide

## For New Users

Follow these steps to install the HubSpot Extended MCP Server:

### Step 1: Download the Project

Download and extract the ZIP file to a location on your computer (e.g., `~/hubspotMcpExtended`).

### Step 2: Install Python Dependencies

Open Terminal (macOS/Linux) or Command Prompt (Windows) and run:

```bash
cd /path/to/hubspotMcpExtended
pip install -r requirements.txt
```

### Step 3: Get Your HubSpot Access Token

1. Log in to your HubSpot account
2. Go to **Settings** → **Integrations** → **Private Apps**
3. Click **"Create a private app"**
4. Name it (e.g., "MCP Server for Claude")
5. Go to the **"Scopes"** tab and enable:
   - ✅ `crm.objects.contacts.read`
   - ✅ `crm.objects.deals.read`
   - ✅ `crm.objects.meetings.read`
   - ✅ `crm.objects.notes.read`
   - ✅ `crm.objects.tasks.read`
   - ✅ `crm.objects.tasks.write`
6. Click **"Create app"**
7. Copy the access token that appears

### Step 4: Configure Environment

Create a file named `.env` in the project folder:

```bash
HUBSPOT_ACCESS_TOKEN=paste_your_token_here
LOG_LEVEL=INFO
```

Replace `paste_your_token_here` with the token you copied in Step 3.

### Step 5: Configure Claude Desktop

#### On macOS:

```bash
open -a "TextEdit" ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

#### On Windows:

Open: `%APPDATA%\Claude\claude_desktop_config.json`

Add this to the file (replace `/FULL/PATH/TO/` with your actual path):

```json
{
  "mcpServers": {
    "hubspot-extended": {
      "command": "python",
      "args": ["/FULL/PATH/TO/hubspotMcpExtended/main_fastmcp.py"],
      "cwd": "/FULL/PATH/TO/hubspotMcpExtended"
    }
  }
}
```

**Example for macOS:**
```json
{
  "mcpServers": {
    "hubspot-extended": {
      "command": "python",
      "args": ["/Users/yourname/hubspotMcpExtended/main_fastmcp.py"],
      "cwd": "/Users/yourname/hubspotMcpExtended"
    }
  }
}
```

**Note:** If you already have other MCP servers configured, just add the `"hubspot-extended"` entry inside the existing `"mcpServers"` object.

### Step 6: Restart Claude Desktop

1. **Completely quit** Claude Desktop (Cmd+Q on macOS, or close from system tray on Windows)
2. **Reopen** Claude Desktop
3. The server should now be available!

### Step 7: Test It

In Claude Desktop, try asking:
```
"Get the meeting details for HubSpot meeting ID 12345"
```

or

```
"Show me my overdue tasks from HubSpot"
```

If configured correctly, Claude will use the HubSpot Extended tools!

## Troubleshooting

### "Command not found: python"

Try using `python3` instead of `python` in the config file:

```json
"command": "python3"
```

### "Cannot find module"

Make sure you installed dependencies:
```bash
cd /path/to/hubspotMcpExtended
pip install -r requirements.txt
```

### Server not showing up in Claude

1. Check your config file syntax (it must be valid JSON)
2. Verify the paths are absolute (full paths, not relative like `~/`)
3. Make sure you completely quit and reopened Claude Desktop
4. Check Claude Desktop logs: **Help → View Logs**

### API Errors

- **401 Unauthorized**: Double-check your `.env` file has the correct token
- **403 Forbidden**: Verify your HubSpot private app has all required scopes

## Need Help?

If you run into issues, check the main [README.md](README.md) for more detailed documentation.
