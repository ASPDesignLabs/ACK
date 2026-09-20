package com.example.besu.computer

import com.example.besu.backup.*
import kotlinx.serialization.Serializable

// CATEGORY nodes can hold children; ENTRY nodes are the selectable leaves.
// This is stored explicitly rather than inferred from children.isEmpty()
// because a freshly-created, still-empty category must not be mistaken for
// a selectable entry.
@Serializable
enum class ComputerNodeType { CATEGORY, ENTRY }

@Serializable
data class ComputerNode(
    val id: String,
    val label: String,
    val type: ComputerNodeType,
    val children: List<ComputerNode> = emptyList(),

    // PRE/POST hint carried over from a migrated TargetSlot, so the legacy
    // auto-inject behavior (TargetRepository.processPhrase) can keep working
    // unchanged after migration. Unused by anything else.
    val legacyStrategy: String? = null,

    // Only ever set on an ENTRY node, never a CATEGORY -- an optional
    // contact card (a person or a place) attached to that specific entry.
    // Null/NONE means "no card"; see ContactCard below.
    val contactCard: ContactCard? = null
)

// NONE means the entry has no contact card. PERSON and PLACE each surface a
// different subset of ContactCard's fields in the editor -- see ContactCard.
@Serializable
enum class ContactCardType { NONE, PERSON, PLACE }

// One day's hours on a PLACE card. enabled = "open this day"; open/close are
// free-text (e.g. "9:00 AM"), matching how every other value in this app is
// a plain text field rather than a dedicated time-picker widget.
@Serializable
data class ContactHours(
    val day: String,
    val enabled: Boolean = false,
    val open: String = "",
    val close: String = ""
)

val CONTACT_CARD_DAYS = listOf("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
private val CONTACT_CARD_DEFAULT_HOURS = CONTACT_CARD_DAYS.map { ContactHours(day = it) }

// All fields a contact card could ever hold, regardless of type -- toggling
// an entry between PERSON and PLACE (or back to NONE) in EDIT ENTRY only
// changes which subset the editor shows, it never discards what's already
// been filled in on the other type's fields.
//
// name is PLACE-only (a formal name distinct from the entry's own short
// label, e.g. label "Tops" / name "Tops Friendly Markets"). PERSON has no
// separate name field -- the entry's own label already is the person's
// name. phone and address are shared by both types. email and the three
// socials are PERSON-only; hours is PLACE-only.
@Serializable
data class ContactCard(
    val type: ContactCardType = ContactCardType.NONE,
    val name: String = "",
    val phone: String = "",
    val address: String = "",
    val email: String = "",
    val socialX: String = "",
    val socialFacebook: String = "",
    val socialLinkedIn: String = "",
    val hours: List<ContactHours> = CONTACT_CARD_DEFAULT_HOURS
)

@Serializable
data class ComputerCategory(
    // Stable identity a [COMPUTER:id] tag binds to. Never changes after
    // creation -- renaming a category only ever changes `label`, so saved
    // phrase templates never go stale.
    val id: String,
    val label: String,
    val persistUntilCleared: Boolean = true,
    val order: Int = 0,

    // The single active pick for this root category, or null for none.
    // One category has exactly one active entry at a time.
    val activeNodeId: String? = null,

    // root.type is always CATEGORY; root.label is unused (category.label is
    // what's shown -- root exists purely to hold top-level children).
    val root: ComputerNode
)
