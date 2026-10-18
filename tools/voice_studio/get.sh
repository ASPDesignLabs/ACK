#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# A signpost, not the installer. ACK Voice Studio moved to its own repository, and this address is kept only so that an old command, guide or setup program says where it went
# instead of failing with "404: Not Found". It fetches nothing, installs nothing and changes nothing. Exit code 2 is this project's "nothing was done".
cat <<'MSG'
ACK Voice Studio now has its own repository, and this address no longer installs it. Nothing was fetched and nothing was changed.

To install it, run this instead:

  curl -fsSL https://raw.githubusercontent.com/ASPDesignLabs/ACK-Voice-Studio/main/tools/voice_studio/get.sh | bash

Your projects and recordings are in ~/ack-voice-studio and are not touched by any of this. If you already have a folder ~/ack-tools that was fetched from the ACK
repository, the new command leaves it as it is and tells you how to move it aside first.
MSG
exit 2
