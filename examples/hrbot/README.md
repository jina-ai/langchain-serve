# 🤖👔 LangChain-powered HR Slack Bot

Leveraging the power of Langchain, we present a guide to building and deploying a LLM-powered HR Slack bot. Langchain simplifies the creation of potent LLM applications, while Langchain-serve enables seamless cloud deployment, bringing these applications closer to users and enhancing accessibility.

In this guide, we focus on constructing a Slack bot specifically designed to automate and streamline HR tasks and interactions. This bot, powered by internal PDF documents on Google Drive, is an essential tool for both employees and the HR team, promoting efficiency and engagement in the workspace. Harness the potential of Langchain and Langchain-serve to make complex tasks manageable and transform your HR processes.

<table align="center" id="hrbot-demo">
  <thead>
    <tr>
      <th colspan="2" style="text-align:center;">HR Bot helping a new employee & the HR team with onboarding & queries about the HR policies</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td valign="middle"><img src="../../.github/images/slack-hrbot-thread-1.png" width="400"/></td>
      <td valign="middle"><img src="../../.github/images/slack-hrbot-thread-2.png" width="400"/></td>
    </tr>
    <tr>
      <td align="center">1</td>
      <td align="center">2</td>
    </tr>
    <tr>
      <td valign="middle"><img src="../../.github/images/slack-hrbot-thread-3.png" width="400"/></td>
      <td valign="middle"><img src="../../.github/images/slack-hrbot-thread-4.png" width="400"/></td>
    </tr>
    <tr>
      <td align="center">3</td>
      <td align="center">4</td>
    </tr>
  </tbody>
</table>


### 👉 Step 1: Install langchain-serve

Let's start by installing langchain-serve if you haven't already

```bash
pip install langchain-serve
```

To get this example code on your local, you can clone this repo and navigate to the `examples/hrbot` directory.

```bash
git clone https://github.com/jina-ai/langchain-serve.git
cd langchain-serve/examples/hrbot
```

### 👉 Step 2: Create the app manifest

Slack apps can be created from scratch or, from a manifest. You can copy the following manifest and use it to create your app.
```yaml
display_information:
  name: langchain-hrbot
  background_color: "#25272e"
features:
  bot_user:
    display_name: langchain-hrbot
    always_online: true
  slash_commands:
    - command: /refresh-gdrive-index
      url: https://your-app.wolf.jina.ai/slack/events
      description: Refresh GDrive Index
      should_escape: false
    - command: /remove-gdrive-index
      url: https://your-app.wolf.jina.ai/slack/events
      description: Remove GDrive index from workspace
      should_escape: false
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
      - commands
settings:
  event_subscriptions:
    request_url: https://your-app.wolf.jina.ai/slack/events
    bot_events:
      - app_mention
      - message.im
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
                                                              
```

### 👉 Step 3: Create the app and configure it

- Go to [slack apps](https://api.slack.com/apps?new_app=1) page.
- Choose `From an app manifest` and pick the workspace you want to install the app in.
- Paste the YAML manifest from the previous step and click `Create`.

You will be redirected to the app configuration page. Your app needs 2 tokens to work.

- **Signing Secret**

    - This is used to verify that the request is coming from Slack. 
    - You can find it under `Basic Information` -> `App Credentials` -> `Signing Secret`. Copy it and save it somewhere safe. 
    - It'd be used as `SLACK_SIGNING_SECRET` in the next step.

- **Bot User OAuth Token**

    - This is used to authenticate the bot user. 
    - To get a token, you'd first need to install it to your workspace. Go to `Install App` -> `Install to Workspace`. You will be asked to authorize the app. Once you do that, you will be redirected back to the app configuration page. 
    - You can find the token under `OAuth & Permissions` -> `OAuth Tokens for Your Workspace`. Copy it and save it somewhere safe. 
    - It'd be used as `SLACK_BOT_TOKEN` in the next step.

### 👉 Step 4: Create the required `.env` file

Create a `.env` file with the following content. Replace the values with the ones you got in the previous step. Without these, the bot won't be able to authenticate itself with Slack.

```bash
SLACK_SIGNING_SECRET=<your-signing-secret>
SLACK_BOT_TOKEN=<your-bot-token>
OPENAI_API_TOKEN=<your-openai-api-token>
```

### 👉 Step 5: Create your GDrive service account and download the credentials

This hrbot builds on the following documents (created by ChatGPT)

- [Team Communications Guide](https://drive.google.com/file/d/1XgUcM2f1l6RsqjpyX4PIW5gLFDwNn1Qq/view?usp=drive_link)
- [Leave Policy](https://drive.google.com/file/d/1K21DMGm5ofH-k9qVGvez9nJ5U4lAByRE/view?usp=drive_link)
- [Code of Conduct](https://drive.google.com/file/d/1ugoWUfXizs1_PoYFiut2egIHMXhLZJZJ/view?usp=drive_link)
- [Remote Work Policy](https://drive.google.com/file/d/14OYFJO3tywOTE6a06aVqAN5-A5zFtDIu/view?usp=drive_link)
- [Zac's Onboarding Guide](https://drive.google.com/file/d/1h4dwvENHHNVmU4ug2Zp3Bm6-bd4P_XxW/view?usp=drive_link)


To allow the bot to access the pdf files in your GDrive, you need to create a service account and download the credentials. You can read more about it [here](https://developers.google.com/identity/protocols/oauth2/service-account#creatinganaccount). Once you have the credentials, save it as `gdrive-service-account.json` in the `examples/hrbot` directory.

### 👉 Step 6: Deploy the app

You can deploy the app using the following command.

```bash
lc-serve deploy jcloud app --env .env
```

<p align="center">
  <img src="../../.github/images/slack-hrbot-deploy.png" alt="Slack Deploy" width="60%"/>
</p>

### 👉 Step 7: Configure the app to use the deployed URL

1. Go to `Event Subscriptions` -> `Request URL` and set it to the Events URL you got in the previous step. Upon saving, Slack will send a request to the URL to verify it. If everything is configured correctly, you will see a green Verified checkmark. If you see an error instead, check the logs of the deployment on [Jina AI Cloud](https://cloud.jina.ai/user/flows).

<p align="center">
  <img src="../../.github/images/slack-hrbot-requests-url.png" alt="Slack Request URL" width="60%"/>
</p>

2. Go to `Slash Commands` and edit the `/refresh-gdrive-index` & `/remove-gdrive-index` commands. Set the Request URL to the Events URL you got in the previous step. 

<p align="center">
  <img src="../../.github/images/slack-hrbot-slash-command.png" alt="Slack Slash Command" width="60%"/>
</p>


### 👉 Step 8: Use the bot in your workspace

You can now use the bot in your workspace. Make sure you invite the bot to the channel you want to use it in. You can do that by typing `/invite @langchain-hrbot` in the channel.


By default, the bot doesn't have access to any of your documents. We've added 2 slash commands to help you with that.

- **Refresh index from Google drive** - You can give it access to your documents by typing `/refresh-gdrive-index` in the channel. This will index all the pdf files in your GDrive, create `Tools` from them and save it in the workspace. You can then use the bot to ask questions about the internal documents relevant to your company.
- **Remove index from Google drive** - You can remove the index by typing `/remove-gdrive-index` in the channel. This will remove the index from the workspace.

<table>
  <tr>
    <td align="center">
      <img src="../../.github/images/slack-commands.png" alt="Slack Commands" width="70%"/>
    </td>
    <td align="center">
      <img src="../../.github/images/slack-command-refresh.png" alt="Slack Demo" width="90%"/>
    </td>
  </tr>
</table>

Once the index is created, you can ask the bot questions about the internal documents. You can do that by mentioning the bot in the channel and asking the question. For example, `@langchain-hrbot what is the leave policy?`. The bot will then use the question to search the index and answer it. 

[Check out the demo at the top of this page to see it in action](#hrbot-demo).
