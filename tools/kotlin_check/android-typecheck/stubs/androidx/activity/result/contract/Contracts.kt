// SPDX-License-Identifier: GPL-3.0-or-later
package androidx.activity.result.contract
import android.net.Uri
object ActivityResultContracts {
    abstract class Contract<I, O>
    class RequestPermission : Contract<String, Boolean>()
    class CreateDocument(mimeType: String) : Contract<String, Uri?>()
}
