# --- ACK DATA PROTECTION ---
# Keep the names of variables in these classes so JSON Export/Import works.
# If R8 renames 'userProfile' to 'a', the JSON won't match.

-keep class com.example.besu.backup.AckBackup { *; }
-keep class com.example.besu.backup.DspConfig { *; }
-keep class com.example.besu.data.QuickPhrase { *; }
-keep class com.example.besu.data.MatrixNode { *; }

# Keep the TransferManager utilities
-keep class com.example.besu.backup.TransferManager { *; }

# --- KOTLIN SERIALIZATION ---
# Ensure the serialization plugin helper classes aren't stripped
-keepattributes *Annotation*, InnerClasses
-dontwarn sun.misc.Unsafe
-keep class kotlinx.serialization.** { *; }

# --- ML KIT (QR SCANNER) ---
# Usually handles itself, but safe to keep just in case
-keep class com.google.mlkit.** { *; }
