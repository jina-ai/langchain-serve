# Langchain Slack Bot

## Setup

### Step 1: Install Langchain Serve

Let's start by installing langchain-serve if you haven't already

```bash
pip install langchain-serve
```

### Step 2: Create the app manifest

Slack apps can be created from scratch or from a manifest. We have a command to generate the manifest for you.

```bash
lcserve util slack-app-manifest --name <custom-name>
```

This will generate a manifest like the following. You can also copy this and use it to create your app.
```yaml
──────────────────────────────────────── App Manifest ────────────────────────────────────────
                           Copy this yaml to create your Slack App.                           
──────────────────────────────────────────────────────────────────────────────────────────────
display_information:                                                                          
  name: langchain-bot                                                                         
features:                                                                                     
  bot_user:                                                                                   
    always_online: true                                                                       
    display_name: Langchain Bot                                                            
oauth_config:                                                                                 
  redirect_urls:                                                                              
  - https://cloud.jina.ai/                                                                    
  scopes:                                                                                     
    bot:                                                                                      
    - app_mentions:read                                                                       
    - channels:history                                                                        
    - chat:write                                                                              
    - groups:history                                                                          
    - groups:read                                                                             
    - im:history                                                                              
    - im:read                                                                                 
    - im:write                                                                                
    - users.profile:read                                                                      
    - channels:read                                                                           
settings:                                                                                     
  event_subscriptions:                                                                        
    bot_events:                                                                               
    - app_mention                                                                             
    - message.im                                                                              
    request_url: https://your-app.wolf.jina.ai/slack/events                                   
  org_deploy_enabled: false                                                                   
  socket_mode_enabled: false                                                                  
  token_rotation_enabled: false                                                               
                                                                                              
──────────────────────────────────────────────────────────────────────────────────────────────
```

### Step 3: Create the app and configure it

- Go to [slack apps](https://api.slack.com/apps?new_app=1) page.
- Choose `From an app manifest` and pick the workspace you want to install the app in.
- Paste the YAML manifest from the previous step and click `Create`.

You will be redirected to the app configuration page. Your app needs 2 tokens to work.

- `Signing Secret` 

This is used to verify that the request is coming from Slack. You can find it under `Basic Information` -> `App Credentials` -> `Signing Secret`. Copy it and save it somewhere safe. It'd be used as `SLACK_SIGNING_SECRET` in the next step.

- `Bot User OAuth Token`

This is used to authenticate the bot user. To get a token, you'd first need to install it to your workspace. Go to `Install App` -> `Install to Workspace`. You will be asked to authorize the app. Once you do that, you will be redirected back to the app configuration page. You can find the token under `OAuth & Permissions` -> `OAuth Tokens for Your Workspace`. Copy it and save it somewhere safe. It'd be used as `SLACK_BOT_TOKEN` in the next step.

### Step 4: Run the bot

```bash
```