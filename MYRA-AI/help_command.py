NETCONTROL_HELP_COMMANDS = """
=== NetControl Commands ===

check network -> Show internet status
scan wifi -> Show nearby WiFi
internet off -> Disable internet (simulated)
internet on -> Enable internet
block site <name> -> Block a website
start focus mode -> Start focus session
stop focus mode -> Stop focus
study mode on -> Ask duration and start strict timer lock
study mode on 2 hours -> Start strict timer lock directly
study mode off -> Ask for passcode and disable study mode
study mood on -> Same as study mode on
study mood off -> Same as study mode off
2 hours / 30 min -> Duration reply while Study Mode is waiting
1234 -> Default unlock passcode when Study Mode asks
start vision monitoring -> Start face, focus, and noise monitoring during Study Mode
stop vision monitoring -> Pause vision monitoring while Study Mode stays active
show vision monitoring status -> Show current face/focus/noise monitor state
show logs -> Show activity logs
open netcontrol dashboard -> Open dashboard UI

Study mode rule -> Sirf MYRA Dashboard, ChatGPT, aur VS Code allowed hain. Supported browser sirf ChatGPT aur localhost ke liye restricted rahega; baaki apps/sites block ya close ho jayenge.

=== WhatsApp Commands ===

open whatsapp -> Open WhatsApp
love ko block kar do -> Ask confirmation and block Love on desktop WhatsApp
rahul ko unblock kar do -> Ask confirmation and unblock Rahul on desktop WhatsApp
mom ko message bhej hello -> Send "hello" to Mom on WhatsApp
haan / nahi -> Confirm or cancel pending WhatsApp block/unblock action
""".strip()


def get_netcontrol_help() -> str:
    return NETCONTROL_HELP_COMMANDS
