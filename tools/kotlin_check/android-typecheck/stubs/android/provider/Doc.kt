// SPDX-License-Identifier: GPL-3.0-or-later
package android.provider
import android.content.ContentResolver
import android.net.Uri
object DocumentsContract { fun deleteDocument(resolver: ContentResolver, uri: Uri): Boolean = true }
