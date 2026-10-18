# SPDX-License-Identifier: GPL-3.0-or-later
# A signpost, not the installer. ACK Voice Studio moved to its own repository, and this address is kept only so that an old command, guide or setup program says where it went
# instead of failing with "404: Not Found". It downloads nothing, installs nothing and changes nothing. It does not call `exit`, because this file is run with `irm ... | iex`
# and `exit` would close the person's PowerShell window before they could read it.
Write-Host ''
Write-Host 'ACK Voice Studio now has its own repository, and this address no longer installs it. Nothing was downloaded and nothing was changed.'
Write-Host ''
Write-Host 'To install it, run this instead:'
Write-Host ''
Write-Host '  irm https://raw.githubusercontent.com/ASPDesignLabs/ACK-Voice-Studio/main/tools/voice_studio/install.ps1 | iex'
Write-Host ''
Write-Host 'Your projects and recordings are in the ack-voice-studio folder of your Ubuntu home and are not touched by any of this.'
