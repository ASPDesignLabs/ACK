# --- ACK DATA PROTECTION ---
# Keep the names of variables in these classes so JSON Export/Import works.
# If R8 renames 'userProfile' to 'a', the JSON won't match.

-keep class com.example.besu.AckBackup { *; }
-keep class com.example.besu.DspConfig { *; }
-keep class com.example.besu.QuickPhrase { *; }
-keep class com.example.besu.MatrixNode { *; }

# Keep the TransferManager utilities
-keep class com.example.besu.TransferManager { *; }

# --- KOTLIN SERIALIZATION ---
# Ensure the serialization plugin helper classes aren't stripped
-keepattributes *Annotation*, InnerClasses
-dontwarn sun.misc.Unsafe
-keep class kotlinx.serialization.** { *; }

# --- ML KIT (QR SCANNER) ---
# Usually handles itself, but safe to keep just in case
-keep class com.google.mlkit.** { *; }
