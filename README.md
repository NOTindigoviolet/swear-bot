# Swear Bot

A powerful and efficient Discord bot designed to scan server message history and generate leaderboards based on the usage of specific, customisable words.

## Features

-   **Full Server Scan**: Scans the entire message history of all text channels in a server.
-   **High-Speed Parallel Scanning**: Uses `asyncio` to scan multiple channels concurrently, making the process significantly faster on servers with many channels.
-   **Customisable Word List**: The list of words to count is not hardcoded. It's loaded from an external `profanity.txt` file, which can be easily modified without touching the code.
-   **Detailed Leaderboards**: Provides slash commands to display leaderboards for the total count of all tracked words, as well as for each individual word.
-   **Data Persistence**: Saves the raw message data to a `data.csv` file after a scan, allowing for further analysis if needed.
-   **Modern Slash Commands**: All user-facing commands are implemented as modern, easy-to-use Discord slash commands.
-   **Owner-Only Access**: The powerful `/scan` command is restricted to the bot owner for security and control.

## Setup and Installation

Follow these steps to get the bot running on your own server.

### 1. Prerequisites

-   Python 3.8 or newer
-   A Discord Bot Token. You can get one from the [Discord Developer Portal](https://discord.com/developers/applications).

### 2. Clone the Repository

```bash
git clone <your-repository-url>
cd swear-bot
```

### 3. Install Dependencies

It's recommended to use a virtual environment.

```bash
# Install required libraries
pip install discord.py pandas python-dotenv
```

### 4. Configure the Bot

1.  **Create a `.env` file** in the root directory and add your Discord bot token:
    ```
    # .env
    DISCORD_TOKEN=YourBotTokenGoesHere
    ```

2.  **Create a `profanity.txt` file** in the root directory. Add the words you want to track, with one word per line. The bot will read this file on startup.
    ```
    # profanity.txt
    word1
    word2
    anotherword
    ```

### 5. Run the Bot

```bash
python main.py
```

## Commands

All commands are slash commands.

### `/scan`
**Owner-only.** This command initiates a full scan of the server.
-   It fetches the entire message history from every text channel in parallel.
-   Saves all collected messages to `data.csv`.
-   This command can take a long time to run on very large servers.

### `/analyse`
**Owner-only.** Compiles the word usage statistics for all users.

### `/leaderboard [category]`
Displays the word usage leaderboards.
-   **`category` (Optional):**
    -   If left empty, it shows the leaderboard for the **total** count of all tracked words.
    -   If you provide a specific word (e.g., `word1`), it shows the leaderboard for just that word.
    -   If you provide a specific user, it shows the breakdown for that user.
    -   If you use `breakdown`, it shows a detailed table with counts for every user and every word.
    -   If you use `percentage`, it shows the leaderboard the for percent of swear words used to total words used.