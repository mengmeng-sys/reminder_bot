# 🎯 Task Coach Bot

A Telegram bot that helps you **break big tasks into small steps, start on
time, and stay focused until the work is done**. It is more than a reminder
bot: it coaches you through the whole task.

Built with Python, [python-telegram-bot](https://python-telegram-bot.org/),
and SQLite.

---

## ✨ Features

### 🪜 Break a big task into steps
- Create a task with a title, a deadline, a time estimate and small steps
- Quick deadlines: **Today 20:00**, **Tomorrow 09:00**, **In 3 days**, or a
  full month calendar with hour and minute pickers
- A task card with a **progress bar** (`▓▓▓░░░░░░░ 30%`) and **one next step**
- Add, edit, delete and tick off steps
- A celebration message when all steps are done

### 🚦 Smart deadline alerts
- Calculates the **latest start time** = deadline − estimate − 20% buffer
- Alerts at **1 day**, **3 hours**, **latest start**, **1 hour**, and
  **overdue**
- The tone gets more urgent over time: 📌 → ⏳ → 🚦 → 🔥 → ⚠️
- A background job checks every 30 seconds, sends each alert once, and only
  sends the **most urgent** missed alert after a restart
- Alerts have buttons: **▶ Start focus**, **✅ Finish next step**,
  **⏭ Snooze 30 min**, **📅 Change deadline**
- **My tasks** shows urgency icons: 🟢 plenty of time, 🟡 start soon,
  🔴 start now / overdue

### 🎯 Focus timer (Pomodoro)
- Choose a task (or no task) and a timer: **15 / 25 / 45 min**
- Halfway check-in: **"Still working? 💪"**
- Time-up screen with **✅ Finish next step**, **☕ Take a 5 min break**,
  **▶ Another round**, **⏹ Finish**
- Break timer with **▶ Start next round**
- Focus time is saved and shown on the task card
- Only one session at a time, and it **survives a bot restart**

---

## 🧰 Requirements

- Python **3.11** or newer
- A Telegram bot token (free, from [@BotFather](https://t.me/BotFather))

---

## 🚀 How to run the bot

### 1. Get a bot token

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the instructions.
3. Copy the token.

### 2. Create the `.env` file

```bash
cd task-coach
cp .env.example .env
```

Open `.env` and paste your token:

```
BOT_TOKEN=123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> 🔒 Never share this file. It is in `.gitignore`.

### 3. Install the packages

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Start the bot

```bash
python bot.py
```

You should see `Bot is running...`. Press `Ctrl+C` to stop.

---

## 📖 How to use it

Send `/start` to see the main menu:

```
👋 Hi, Dara!

I'm your task coach. I'll help you:
🪜 break big tasks into small steps
🚦 start on time
🎯 stay focused until the work is done

[➕ New task]  [📋 My tasks]
[🎯 Focus]     [❓ Help]
```

The commands are: `/start` · `/new` · `/tasks` · `/focus` · `/help`

---

## 🧪 Test each feature step by step in Telegram

### Feature 1 — Break a big task into steps

1. Send `/start` and tap **➕ New task**.
2. Type a title, for example `Finish report`.
3. Tap **Tomorrow 09:00**.
4. Tap **2 h**.
5. Send the steps, one per line:
   ```
   Write the introduction
   Make the chart
   Proofread
   ```
6. Look at the task card: title, 🗓 deadline with countdown, ⏱ estimate,
   🚦 start-by time, 🪜 progress bar, 👉 next step, 🎯 focus time.
7. Tap **✅ Finish next step**. The progress bar goes to `1/3` and the next
   step changes.
8. Tap **🪜 All steps**. You should see `☑ 1. Write the introduction` and
   `☐ 2. Make the chart`.
9. Tap a step to toggle it done / not done.
10. Tap **➕ Add step** and send `Check references`.
11. Tap **✏️ Edit**, choose a step, send the new text.
12. Tap **🗑 Delete**, choose a step, confirm.
13. Tap **🎯 Focus on this** — the timer picker should appear.
14. Tap **🗑 Delete task** and confirm. The task disappears from **My tasks**.
15. Try **Skip, add steps later** when creating a task: the card should show
    `🪜 No steps yet` and an **➕ Add step** button.

### Feature 2 — Smart deadline alerts

1. Create a task with a deadline about **10 minutes** from now and a **1 h**
   estimate. The card should show
   `⚠️ You are already late to start. Start now!`.
2. Create a task with a deadline about **2 hours** from now and a **30 min**
   estimate. Wait for the **🚦 Time to start!** alert (about 1.5 hours
   before the deadline).
3. Check that the alert shows the task card, the next step and the buttons
   **▶ Start focus**, **✅ Finish next step**, **⏭ Snooze 30 min**,
   **📅 Change deadline**.
4. Tap **⏭ Snooze 30 min** — you should get another alert 30 minutes later.
5. Tap **📅 Change deadline**, pick a new day and time, confirm. The alerts
   should be rebuilt for the new deadline.
6. Finish all the steps of a task. You should get
   `🎉 Task completed! Great job.` and **no more alerts** for that task.
7. Open **📋 My tasks** and check the urgency icons: 🟢, 🟡 and 🔴.
8. To test the "missed alert" rule: create a task, stop the bot, wait a few
   minutes, then start the bot again. You should get **only the most urgent**
   missed alert, not all of them.

### Feature 3 — Focus timer

1. Tap **🎯 Focus**, choose a task, then tap **25 min**.
2. You should see `🎯 Focus started. Ends at 14:25` with a **⏹ Stop** button.
3. Wait for the halfway check-in (about 12 minutes): **"Still working? 💪"**.
   Tap **👍 Yes**.
4. When the timer ends you should see
   **⏰ Time is up! Great focus.** with four buttons.
5. Tap **✅ Finish next step** — the next step of the task is marked done.
6. Tap **▶ Another round** — a new 25 minute session starts.
7. Tap **☕ Take a 5 min break** — you should see `☕ Break until 14:30`.
8. When the break ends, tap **▶ Start next round**.
9. Tap **⏹ Stop** during a session — the session ends and the focus time is
   added to the task card.
10. Restart the bot while a session is running. The session should still be
    there when you reopen **🎯 Focus**.

---

## 🗂 Project structure

| File | What it does |
|------|--------------|
| `bot.py` | Starts the bot, registers handlers, sets the command list |
| `config.py` | Reads `.env`, the time zone and the database path |
| `database.py` | All SQL: users, tasks, steps, alerts, focus sessions |
| `utils.py` | Time maths: latest start, alert schedule, time left, progress bar |
| `messages.py` | All text templates: menu, task card, steps, alerts, focus |
| `keyboards.py` | Every inline keyboard, including the month calendar |
| `jobs.py` | Background jobs: alert checker and focus timer |
| `handlers/menu.py` | `/start`, `/help`, the 🏠 Menu button |
| `handlers/tasks.py` | New task flow, task card, my tasks, change deadline |
| `handlers/steps.py` | Steps screen, add / edit / delete steps |
| `handlers/focus.py` | Focus timer flow |
| `handlers/alerts.py` | Buttons on alert messages |
| `tests/` | Tests that do not need Telegram |

---

## 🕰 How the time zone works

- **The database always stores UTC.** For example, 18:00 in Cambodia
  (UTC+7) is stored as `11:00`.
- **The bot always shows Asia/Phnom_Penh time.** When it reads a time from
  the database, it converts it to UTC+7 before showing it.

The helpers live in `utils.py`:

- `utc_now()` — current time in UTC
- `to_local(dt)` — UTC → Cambodia time
- `local_to_utc(day, hour, minute)` — Cambodia time → UTC
- `latest_start_time(deadline, estimate)` — deadline − estimate − 20% buffer
- `alert_schedule(deadline, estimate)` — the five alert times
- `time_left_text(deadline)` — `⏳ 2 days left`, `⚠️ Overdue by 3 h`, ...
- `progress_bar(done, total)` — `▓▓▓░░░░░░░ 30%`

---

## 🧪 Tests

The tests do not need a real bot token or an internet connection:

```bash
python -m pytest
```

They check the latest start time, the alert schedule, the progress bar, the
time-left text, the database, the task card, the button wiring and the whole
create-task flow.

---

## 🛠 Troubleshooting

### "Could not connect to Telegram" or `TimedOut`

The bot gives Telegram **30 seconds** to answer and retries **3 times**. If it
still cannot connect:

1. Check your internet connection.
2. Check whether Telegram is blocked by your internet provider.
3. If it is blocked, use a proxy. Add it to `.env`:
   ```
   PROXY_URL=http://127.0.0.1:7890
   ```
   For a SOCKS5 proxy, also run `pip install socksio`.

### "BOT_TOKEN is missing"

Create `.env` from `.env.example` and paste your token.

### The bot is not responding

Make sure only **one** copy of the bot is running.

---

## 🌱 Built to grow

The structure is ready for future features (for example: recurring tasks,
task categories, priority levels, streaks and statistics). The database
tables and handler modules are kept small so new features can be added
without rewriting the bot.
