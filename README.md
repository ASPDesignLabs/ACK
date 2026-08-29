BESU 🖖


A Physics-Driven AAC & Social Protocol Engine

  

BESU is a multimodal Augmentative and Alternative Communication (AAC) system designed to bridge the gap between physical intent and digital expression. Unlike traditional grid-based AAC apps that require fine motor control and visual focus, BESU utilizes a distributed architecture (Phone + Watch) to enable "blind" communication through proprioceptive gestures and context-aware interfaces.

It functions as a digital emotional prosthesis, allowing users to project complex needs, emotions, and social protocols onto their environment instantly using physics-based triggers.


---

🌟 Key Differentiators

1. The Physics Engine (Wear OS)


BESU moves beyond simple tap detection. The watch module runs a custom sensor fusion algorithm that analyzes Accelerometer (Gravity/Pose) and Gyroscope (Rotation Velocity) data in real-time. It implements a state-locking mechanism to distinguish between daily noise (walking, typing) and deliberate communicative acts.

2. The "Grammar-First" Radial UI


While most AAC tools force users into "Tarzan speech" (e.g., "Want Apple"), BESU utilizes a hybrid Radial/Linear interface that promotes natural syntax.


- Context Rows: Permanently accessible grammar particles ("To", "The", "With") allow for rapid sentence construction.

- Smart History: An LRU (Least Recently Used) caching system tracks your most used phrases and creates an endless, scrollable history bar.

- Drill-Down Logic: Infinite nesting allows broad concepts ("Hungry") to drill down into specifics ("Dinner" -> "Pizza") without losing the ability to trigger the parent concept.

3. Social Protocol Macros


BESU automates social friction points. Gestures like "My Name Is..." read user-defined profile data to generate spoken introductions, while "Nice to Meet You" automates polite greetings through broad arm sweeps, allowing users to participate in social rituals without verbal strain.


---

🛠️ Installation & Setup

Prerequisites

- Smartphone: Android 10+ (API 29+).

- Smartwatch: Wear OS 3.0+ (Must contain Accelerometer & Gyroscope).

- Environment: Android Studio Ladybug (or newer).

Deployment


This is a multi-module Gradle project (:app and :wear).


1. Clone the Repository:

	git clone https://github.com/ASPDesignLabs/BESU-AAC.git



2. Enable Debugging:
	- Phone: Settings > Developer Options > USB Debugging.

	- Watch: Settings > Developer Options > ADB Debugging & Debug over Wi-Fi.


3. Pairing: Ensure the watch is paired to the phone via the official Wear OS app.

4. Install :app (Phone):
	- Select the app configuration in Android Studio.

	- Run on the connected Phone.

	- Permissions: On first launch, you must grant "Display Over Other Apps" when prompted.


5. Install :wear (Watch):
	- Select the wear configuration.

	- Run on the connected Watch.

	- Note: If using an Emulator, forward the port: adb -d forward tcp:5601 tcp:5601



---

🎮 Gesture Interaction Guide


The BESU sensor engine uses a Pose & Pause state machine. To trigger a command, you generally Enter a Pose, Wait (500ms), and then Execute.

1. The Unlock (Safety Gate)

- Prevents accidental triggers while walking or resting.

- Pose: Hold arm horizontal across chest (looking at watch).

- Action: Quickly rotate wrist Away (Palm Up) then Back (Palm Down) twice.

- Feedback: Watch vibrates and turns GREEN ("UNLOCKED").

2. "Thumbs Up" / "Yes" / "Good"

- Uses gravity gating to detect a deliberate pump.

- State 1 (Prime): Raise fist to vertical (AccX > 7.0). Watch text turns YELLOW ("PRIMED").

- State 2 (Fire): Drop fist down quickly (AccX < 4.0).

- Output: "That is good."

3. "No" / "Refusal"

- Designed to mimic a natural "Wiper" motion low by the hip.

- Pose: Arm relaxed, pointing downwards (Below horizontal).

- Action: Twist wrist rapidly 3 times.

- Logic: Checks for strong Z-axis rotation while Gravity X is negative.

- Output: "No. I don't want that."

4. "Stop" / "Hand"

- Distinguishes from Thumbs Up by reading the Y-Axis gravity vector.

- Pose: Extend arm straight forward, palm facing away (Traffic Cop).

- Action: Hold perfectly still for 0.5 seconds.

- Logic: AccY dominates gravity (watch 6 o'clock is down), Gyro sum must be near 0.

- Output: "Please stop."

5. "Hello" / "Wave"

- Uses Gyroscope summation to detect wiggling while elevated.

- Pose: Arm raised high (AccX > 5.0).

- Action: Wave hand side-to-side (4 direction changes).

- Output: "Hello there."

6. "My Name Is..." (Social Macro)

- Horizontal twist logic.

- Pose: Arm held perfectly horizontal (Level).

- Action: Distinct wrist roll (Out -> In -> Out).

- Logic: Differentiates from "No" by ensuring AccX is near 0.

- Output: "My name is [User Profile Name]." (Configurable in Phone App).

7. "Nice To Meet You" (Compound Macro)

- A two-stage complex gesture.

- Stage 1: Raise arm and wiggle (Start a Wave).

- Stage 2: Immediately Sweep arm wide to the side (Forearm rotation).

- Output: "Nice to meet you."


---

📱 The Radial Interface (Phone)


When gestures aren't enough, the Phone UI provides a high-bandwidth communication array.

The 4-Row Context System


Surrounding the central Emotion Wheel are four scrollable context bars:


- Top Row (Gold): Smart History
	- Contains your most frequently used items and context-aware suggestions (e.g., showing "Breakfast" items only in the morning).


- Top Row 2: Context
	- Who (Me, You, They) and Where (Home, Work, Here).


- Bottom Row 1: Action
	- What (Want, Go, Help) and Needs (Hungry, Thirsty).


- Bottom Row 2: Grammar (Always Visible)
	- Permanent access to linkers: To, The, A, Is, With, And.


Modes

- Instant Mode (Default): Tapping an item speaks it immediately.

- Builder Mode: Tapping items adds them to a sentence buffer at the top of the screen.
	- Example: Tap "I" -> "Want" -> "To" -> "Go" -> "Home".

	- Tap Play to speak the full sentence.

	- Tap Star to save this sentence to your favorites.


Panic Mode 🆘


A dedicated Red SOS button is always visible in the top right corner of the overlay. Tapping this bypasses all buffers and menus to immediately flash the screen and vocalize: "I need help immediately."


---

⚙️ Configuration


Main Activity Settings:


- User Name: Input your name for the "My Name Is" gesture. Note: You must tap Save to commit changes.

- Voice Toggle: Enable/Disable TTS.

- Overlay Visuals: Toggle the large emoji display.

- Sticky Mode: If enabled, the emoji overlay persists until manually tapped (useful for showing a screen to a teacher/peer).

- Sticky Menu: Keeps the Radial Menu open after selection to facilitate rapid sentence building.


---

📂 Project Architecture

- CommunicationData.kt: The "Brain". Contains the JSON loader and data models.

- HistoryManager.kt: The "Memory". Manages LRU caching and Time-of-Day logic.

- RadialMenuService.kt: The "Controller". Manages the overlay window, UI inflation, and state logic.

- WearListenerService.kt: The "Bridge". Listens for high-frequency data packets from the watch.

- assets/communication.json: The "Vocabulary". A compile-free JSON file defining every button, color, phrase, and hierarchy. Edit this file to change the app's language or content.
