// SPDX-License-Identifier: GPL-3.0-or-later
package androidx.activity.compose
import android.net.Uri
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
class ManagedActivityResultLauncher<I, O> { fun launch(input: I) {} }
@Composable
fun BackHandler(enabled: Boolean = true, onBack: () -> Unit) {}
@Composable
fun <I, O> rememberLauncherForActivityResult(contract: ActivityResultContracts.Contract<I, O>, onResult: (O) -> Unit): ManagedActivityResultLauncher<I, O> = ManagedActivityResultLauncher()
