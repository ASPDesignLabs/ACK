# Keep the Sensor Logic intact (sometimes reflection is used for sensors)
-keep class com.example.besu.wear.AckSensor { *; }

# Keep the Synth logic as it uses specific math that shouldn't be over-optimized
-keep class com.example.besu.wear.TechSynth { *; }

# Standard Coroutines rules
-keep class kotlinx.coroutines.** { *; }
