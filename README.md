# AI English Grammar Mentor 🇬🇧🤖

A Telegram bot designed to help users learn English grammar interactively. It acts as a personal AI tutor, providing exercises and intelligent, context-aware hints without giving away the direct answers.

## 🚀 Technologies Used
* **Python 3.10+**
* **Aiogram 3.x** (Asynchronous framework for Telegram Bot API)
* **SQLite** (Relational database for storing theory and exercises)
* **LangChain & Google GenAI (Gemini 2.0 Flash)** (For intelligent user feedback)
* **Asyncio** (For asynchronous task execution)

## 🛠 Key Features

### 1. FSM (Finite State Machine) for Quizzes
The bot uses Aiogram's FSM (`StatesGroup`, `State`) to manage the interactive quiz flow. It tracks:
* The user's current progress (10 questions per unit).
* The number of errors made during the session.
* The IDs of previously answered questions to avoid repetition.

### 2. Intelligent AI Hints (LangChain + Gemini)
When a user makes a mistake, the bot doesn't just say "Wrong." It asynchronously queries the **Gemini 2.0 Flash** model via LangChain. The LLM acts as a tutor, analyzing the specific grammar rule, the question, and the user's incorrect input to generate a short, helpful hint in Russian *without* revealing the correct answer.

### 3. Smart Answer Validation
The bot includes a custom normalization algorithm (`normalize_text`) that handles apostrophes, common English contractions (e.g., "isn't" -> "is not"), and prevents false negatives if a user redundantly types the subject of the sentence.

### 4. Modular Routing and Pagination
* Handlers are organized using Aiogram's `Router` system.
* Implemented dynamic Inline Keyboards for smooth pagination through grammar units.

## 📦 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/your-username/my-english-bot.git](https://github.com/your-username/my-english-bot.git)
   cd my-english-bot
