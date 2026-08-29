#include <jni.h>
#include <cmath>
#include <vector>
#include <stdlib.h>
#include <algorithm> // For std::clamp

#define SAMPLE_RATE 44100
#define PI 3.14159265358979323846

// STYLE CONSTANTS
#define STYLE_CYBER 0
#define STYLE_CLEAN 1
#define STYLE_ORGANIC 2

extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_example_besu_wear_CyberAudio_generateNativeBuffer(
        JNIEnv* env,
        jobject /* this */,
        jint sfxType,
        jint durationMs,
        jint styleId,
        jfloat volume) { // New parameters: Style and Volume (0.0 - 1.0)

    int numSamples = (SAMPLE_RATE * durationMs) / 1000;
    int alignedSamples = (numSamples + 3) & ~3;
    std::vector<int8_t> buffer(alignedSamples);

    for (int i = 0; i < numSamples; i++) {
        double t = (double)i / SAMPLE_RATE;
        double sample = 0.0; // Working in -1.0 to 1.0 range

        // --- DSP ROUTER ---
        switch (styleId) {
            case STYLE_CYBER: // BITCRUSHED / NOISY
                switch (sfxType) {
                    case 0: // UNLOCK: Rising Saw
                        sample = fmod(i * (100.0 + t*400.0) * 0.005, 2.0) - 1.0;
                        sample += ((rand() % 100) / 500.0); // Noise
                        break;
                    case 1: // TICK: Square
                        sample = (i < 400) ? 0.8 : -0.8;
                        break;
                    case 2: // LOCK: Low Saw
                        sample = (sin(t * 60.0 * 2 * PI) > 0 ? 0.8 : -0.8);
                        break;
                    case 3: // MODIFIER: High Sine
                        sample = sin(t * 800.0 * 2 * PI);
                        break;
                    case 4: // FIRE: Static
                        sample = ((rand() % 200) / 100.0) - 1.0;
                        break;
                }
                break;

            case STYLE_CLEAN: // PURE SINES / SMOOTH
                switch (sfxType) {
                    case 0: // UNLOCK: Smooth Arp
                        sample = sin(t * 440.0 * 2 * PI) * 0.5 + sin(t * 880.0 * 2 * PI) * 0.5;
                        break;
                    case 1: // TICK: High Blip
                        sample = sin(t * 1200.0 * 2 * PI);
                        break;
                    case 2: // LOCK: Soft Bass
                        sample = sin(t * 120.0 * 2 * PI);
                        break;
                    case 3: // MODIFIER: Ping
                        sample = sin(t * 1500.0 * 2 * PI) * (1.0 - (t/0.08)); // Decay
                        break;
                    case 4: // FIRE: Chord
                        sample = sin(t * 523.25 * 2 * PI) * 0.33 + sin(t * 659.25 * 2 * PI) * 0.33 + sin(t * 783.99 * 2 * PI) * 0.33;
                        break;
                }
                break;

            case STYLE_ORGANIC: // WOOD / CLICK / PERCUSSIVE
                // Approximating percussive sounds with enveloped noise
                switch (sfxType) {
                    case 0: // UNLOCK: Shaker swell
                        sample = (((rand()%100)/50.0)-1.0) * t;
                        break;
                    case 1: // TICK: Woodblock
                        sample = sin(t * 800.0 * 2 * PI) * exp(-t * 80.0);
                        break;
                    case 2: // LOCK: Thump
                        sample = sin(t * 60.0 * 2 * PI) * exp(-t * 20.0);
                        break;
                    case 3: // MODIFIER: Glass tap
                        sample = sin(t * 2000.0 * 2 * PI) * exp(-t * 100.0);
                        break;
                    case 4: // FIRE: Breath/Air
                        sample = (((rand()%100)/50.0)-1.0) * (1.0 - t);
                        break;
                }
                break;
        }

        // Apply Volume and Shift to 8-bit unsigned (0-255)
        // sample is -1.0 to 1.0. We want 0 to 255. Center is 128.
        int val = (int)(128 + (sample * 127.0 * volume));
        
        // Clamp safely
        if (val > 255) val = 255;
        if (val < 0) val = 0;

        buffer[i] = (int8_t)val;
    }

    jbyteArray result = env->NewByteArray(alignedSamples);
    env->SetByteArrayRegion(result, 0, alignedSamples, buffer.data());
    return result;
}
