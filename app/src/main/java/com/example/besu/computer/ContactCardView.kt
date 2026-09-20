@file:OptIn(ExperimentalFoundationApi::class)

package com.example.besu.computer

import com.example.besu.help.*
import com.example.besu.output.OutputService
import com.example.besu.ui.*
import com.example.besu.ui.theme.*
import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.RowScope
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// The screen a contact card opens into -- reached from EDIT ENTRY's "OPEN
// CONTACT CARD" button, the [CARD] badge on a tree row, or the CONTACT
// CARDS browser at the bottom of TargetView. Combined view/edit, not two
// separate screens: a freshly-created (still-blank) card opens straight
// into editing; anything with data already in it opens in VIEW mode, where
// every filled field is a tap-for-the-relevant-action /
// long-press-to-copy row instead of a text field. [EDIT] toggles between
// the two at any time.
@Composable
fun ContactCardDialog(
    context: Context,
    primaryColor: Color,
    categoryId: String,
    nodeId: String,
    onDismiss: () -> Unit
) {
    val category = remember(categoryId) {
        ComputerRepository.getCategories(context).find { it.id == categoryId }
    }
    val node = category?.let { ComputerRepository.findNode(it, nodeId) }

    LaunchedEffect(node) {
        if (node == null) onDismiss()
    }
    if (node == null) return

    // Local state, not re-read from the repository on every keystroke --
    // same reasoning as MatrixEditor's own live-save template field, so a
    // write-then-reread round trip can never cause the cursor to jump.
    // Every change is still persisted immediately via ComputerRepository.
    var localCard by remember(node.id) { mutableStateOf(node.contactCard ?: ContactCard()) }
    var editing by remember(node.id) { mutableStateOf(isCardBlank(localCard)) }

    fun save(newCard: ContactCard) {
        localCard = newCard
        ComputerRepository.saveContactCard(context, categoryId, nodeId, newCard)
    }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = if (localCard.type == ContactCardType.PLACE) "PLACE CARD" else "PERSON CARD",
        subtitle = node.label
    ) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            Text(
                text = if (editing) "[DONE EDITING]" else "[EDIT]",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .heightIn(min = 44.dp)
                    .clickable { editing = !editing }
                    .padding(horizontal = 4.dp)
            )
        }

        Spacer(modifier = Modifier.height(4.dp))

        if (localCard.type == ContactCardType.PLACE) {
            PlaceCardBody(
                context = context,
                primaryColor = primaryColor,
                entryLabel = node.label,
                card = localCard,
                editing = editing,
                onSave = { save(it) }
            )
        } else {
            PersonCardBody(
                context = context,
                primaryColor = primaryColor,
                entryLabel = node.label,
                card = localCard,
                editing = editing,
                onSave = { save(it) }
            )
        }
    }
}

private fun isCardBlank(card: ContactCard): Boolean =
    card.name.isBlank() && card.phone.isBlank() && card.address.isBlank() &&
        card.email.isBlank() && card.socialX.isBlank() && card.socialFacebook.isBlank() &&
        card.socialLinkedIn.isBlank() && card.hours.none { it.enabled }

@Composable
private fun PlaceCardBody(
    context: Context,
    primaryColor: Color,
    entryLabel: String,
    card: ContactCard,
    editing: Boolean,
    onSave: (ContactCard) -> Unit
) {
    ContactField(
        label = "NAME",
        value = card.name,
        primaryColor = primaryColor,
        editing = editing,
        placeholder = "E.G. TOPS FRIENDLY MARKETS",
        onValueChange = { onSave(card.copy(name = it)) },
        onTap = { speak(context, card.name.ifBlank { entryLabel }) },
        onCopy = { copyToClipboard(context, "NAME", card.name) }
    )
    ContactField(
        label = "PHONE",
        value = card.phone,
        primaryColor = primaryColor,
        editing = editing,
        placeholder = "E.G. (555) 555-1234",
        onValueChange = { onSave(card.copy(phone = it)) },
        onTap = { openDialer(context, card.phone) },
        onCopy = { copyToClipboard(context, "PHONE", card.phone) }
    )
    ContactField(
        label = "ADDRESS",
        value = card.address,
        primaryColor = primaryColor,
        editing = editing,
        placeholder = "E.G. 123 MAIN ST",
        onValueChange = { onSave(card.copy(address = it)) },
        onTap = { openMaps(context, card.address) },
        onCopy = { copyToClipboard(context, "ADDRESS", card.address) }
    )

    Spacer(modifier = Modifier.height(10.dp))
    TightSectionLabel("HOURS")
    Spacer(modifier = Modifier.height(6.dp))
    HoursChecklist(primaryColor = primaryColor, hours = card.hours, editing = editing) { newHours ->
        onSave(card.copy(hours = newHours))
    }
}

@Composable
private fun PersonCardBody(
    context: Context,
    primaryColor: Color,
    entryLabel: String,
    card: ContactCard,
    editing: Boolean,
    onSave: (ContactCard) -> Unit
) {
    // No editable NAME field for a person -- the entry's own label already
    // is their name. Still shown as its own tap-to-speak/long-press-to-copy
    // row for consistency with every other field on the card.
    Column(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        TightSectionLabel("NAME")
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            entryLabel,
            color = primaryColor,
            fontSize = 13.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 44.dp)
                .combinedClickable(
                    onClick = { speak(context, entryLabel) },
                    onLongClick = { copyToClipboard(context, "NAME", entryLabel) }
                )
                .padding(vertical = 6.dp)
        )
    }

    ContactField(
        label = "PHONE",
        value = card.phone,
        primaryColor = primaryColor,
        editing = editing,
        placeholder = "E.G. (555) 555-1234",
        onValueChange = { onSave(card.copy(phone = it)) },
        onTap = { openDialer(context, card.phone) },
        onCopy = { copyToClipboard(context, "PHONE", card.phone) }
    )
    ContactField(
        label = "ADDRESS",
        value = card.address,
        primaryColor = primaryColor,
        editing = editing,
        placeholder = "E.G. 123 MAIN ST",
        onValueChange = { onSave(card.copy(address = it)) },
        onTap = { openMaps(context, card.address) },
        onCopy = { copyToClipboard(context, "ADDRESS", card.address) }
    )
    ContactField(
        label = "EMAIL",
        value = card.email,
        primaryColor = primaryColor,
        editing = editing,
        placeholder = "E.G. NAME@EXAMPLE.COM",
        onValueChange = { onSave(card.copy(email = it)) },
        onTap = { openEmail(context, card.email) },
        onCopy = { copyToClipboard(context, "EMAIL", card.email) }
    )
    ContactField(
        label = "X",
        value = card.socialX,
        primaryColor = primaryColor,
        editing = editing,
        placeholder = "E.G. @HANDLE",
        onValueChange = { onSave(card.copy(socialX = it)) },
        onTap = { openUrl(context, socialUrl("X", card.socialX)) },
        onCopy = { copyToClipboard(context, "X", card.socialX) }
    )
    ContactField(
        label = "FACEBOOK",
        value = card.socialFacebook,
        primaryColor = primaryColor,
        editing = editing,
        placeholder = "E.G. HANDLE",
        onValueChange = { onSave(card.copy(socialFacebook = it)) },
        onTap = { openUrl(context, socialUrl("FACEBOOK", card.socialFacebook)) },
        onCopy = { copyToClipboard(context, "FACEBOOK", card.socialFacebook) }
    )
    ContactField(
        label = "LINKEDIN",
        value = card.socialLinkedIn,
        primaryColor = primaryColor,
        editing = editing,
        placeholder = "E.G. HANDLE",
        onValueChange = { onSave(card.copy(socialLinkedIn = it)) },
        onTap = { openUrl(context, socialUrl("LINKEDIN", card.socialLinkedIn)) },
        onCopy = { copyToClipboard(context, "LINKEDIN", card.socialLinkedIn) }
    )
}

// One field, either an editable text input or -- once it has a value and
// the card isn't in edit mode -- a plain styled row: tap fires the
// field-appropriate action (dial/maps/mail/open link/speak), long-press
// copies the raw value to the clipboard.
@Composable
private fun ContactField(
    label: String,
    value: String,
    primaryColor: Color,
    editing: Boolean,
    placeholder: String,
    onValueChange: (String) -> Unit,
    onTap: () -> Unit,
    onCopy: () -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        TightSectionLabel(label)
        Spacer(modifier = Modifier.height(4.dp))

        if (editing) {
            OutlinedTextField(
                value = value,
                onValueChange = onValueChange,
                singleLine = true,
                placeholder = { Text(placeholder, color = Color.DarkGray, fontFamily = FontFamily.Monospace, fontSize = 12.sp) },
                modifier = Modifier.fillMaxWidth(),
                textStyle = TextStyle(fontFamily = FontFamily.Monospace, fontSize = 13.sp),
                colors = TextFieldDefaults.colors(
                    focusedTextColor = primaryColor,
                    unfocusedTextColor = primaryColor,
                    focusedContainerColor = VoidBlack,
                    unfocusedContainerColor = VoidBlack,
                    focusedIndicatorColor = primaryColor
                )
            )
        } else if (value.isBlank()) {
            Text("--", color = Color.DarkGray, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
        } else {
            Text(
                value,
                color = primaryColor,
                fontSize = 13.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 44.dp)
                    .combinedClickable(onClick = onTap, onLongClick = onCopy)
                    .padding(vertical = 6.dp)
            )
        }
    }
}

@Composable
private fun HoursChecklist(
    primaryColor: Color,
    hours: List<ContactHours>,
    editing: Boolean,
    onChange: (List<ContactHours>) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        hours.forEachIndexed { index, day ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                ContactCardTypeCheckbox(
                    label = day.day,
                    checked = day.enabled,
                    enabled = editing,
                    color = primaryColor
                ) {
                    val updated = hours.toMutableList()
                    updated[index] = day.copy(enabled = !day.enabled)
                    onChange(updated)
                }

                if (day.enabled) {
                    Spacer(modifier = Modifier.width(10.dp))
                    if (editing) {
                        HourTimeField(day.open, primaryColor, "OPEN") { newOpen ->
                            val updated = hours.toMutableList()
                            updated[index] = day.copy(open = newOpen)
                            onChange(updated)
                        }
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("-", color = Color.Gray, fontFamily = FontFamily.Monospace)
                        Spacer(modifier = Modifier.width(6.dp))
                        HourTimeField(day.close, primaryColor, "CLOSE") { newClose ->
                            val updated = hours.toMutableList()
                            updated[index] = day.copy(close = newClose)
                            onChange(updated)
                        }
                    } else {
                        Text(
                            text = "${day.open.ifBlank { "?" }} - ${day.close.ifBlank { "?" }}",
                            color = primaryColor,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun RowScope.HourTimeField(value: String, primaryColor: Color, placeholder: String, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        singleLine = true,
        placeholder = { Text(placeholder, color = Color.DarkGray, fontFamily = FontFamily.Monospace, fontSize = 10.sp) },
        modifier = Modifier.weight(1f),
        textStyle = TextStyle(fontFamily = FontFamily.Monospace, fontSize = 11.sp),
        colors = TextFieldDefaults.colors(
            focusedTextColor = primaryColor,
            unfocusedTextColor = primaryColor,
            focusedContainerColor = VoidBlack,
            unfocusedContainerColor = VoidBlack,
            focusedIndicatorColor = primaryColor
        )
    )
}

// --- OS INTENT / CLIPBOARD HELPERS ---
// No existing precedent for this elsewhere in the app -- established fresh
// here. Every launch is wrapped since there's no guarantee a given device
// has an app installed to handle it (a stripped-down ROM with no dialer,
// no maps app, etc.) -- fails soft with a Toast instead of crashing.

private fun launchOrToast(context: Context, intent: Intent) {
    try {
        context.startActivity(intent)
    } catch (e: ActivityNotFoundException) {
        Toast.makeText(context, "NO APP AVAILABLE FOR THIS ACTION", Toast.LENGTH_SHORT).show()
    }
}

private fun openDialer(context: Context, phone: String) {
    if (phone.isBlank()) return
    launchOrToast(context, Intent(Intent.ACTION_DIAL, Uri.parse("tel:${Uri.encode(phone)}")))
}

private fun openMaps(context: Context, address: String) {
    if (address.isBlank()) return
    launchOrToast(context, Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=${Uri.encode(address)}")))
}

private fun openEmail(context: Context, email: String) {
    if (email.isBlank()) return
    launchOrToast(context, Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:${Uri.encode(email)}")))
}

private fun openUrl(context: Context, url: String) {
    if (url.isBlank()) return
    launchOrToast(context, Intent(Intent.ACTION_VIEW, Uri.parse(url)))
}

// Accepts either a full URL (used as-is) or a bare handle/username (an
// optional leading "@" is stripped), and builds that platform's profile
// URL from it.
private fun socialUrl(platform: String, handleOrUrl: String): String {
    val trimmed = handleOrUrl.trim()
    if (trimmed.isBlank()) return ""
    if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) return trimmed

    val handle = trimmed.removePrefix("@")
    return when (platform) {
        "X" -> "https://x.com/$handle"
        "FACEBOOK" -> "https://facebook.com/$handle"
        "LINKEDIN" -> "https://linkedin.com/in/$handle"
        else -> trimmed
    }
}

private fun copyToClipboard(context: Context, label: String, value: String) {
    if (value.isBlank()) return
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    clipboard.setPrimaryClip(ClipData.newPlainText(label, value))
    Toast.makeText(context, "COPIED", Toast.LENGTH_SHORT).show()
}

// Speaks a name through the same OutputService pipeline as everywhere else
// in the app, rather than a separate one-off TTS call.
private fun speak(context: Context, text: String) {
    if (text.isBlank()) return
    val intent = Intent(context, OutputService::class.java)
    intent.putExtra("phrase", text)
    intent.putExtra("robotic", false)
    intent.putExtra("source", "COMPUTER/CONTACT")
    context.startService(intent)
}
