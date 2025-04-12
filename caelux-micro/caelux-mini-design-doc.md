# Caelux Mini: Comprehensive Design Document

## 1. Overview

Caelux Mini is an advanced FM synthesis engine implemented in Python, designed to create complex, evolving sounds through a hierarchical oscillator architecture. It combines flexible sound design capabilities with intuitive parameter control and a modular approach to synthesis.

## 2. Core Architecture

### 2.1 Oscillator Design

Each oscillator in Caelux Mini is identical in capabilities, regardless of its role as a carrier or operator. Every oscillator includes:

- **Waveform Selection**: Multiple wavetable options (sine, saw, square, formants, etc.)
- **Oscillator Bank**: Variable number of detuned oscillators per voice (1-20)
- **Frequency Control**: Ratio/fixed modes, ramps, envelopes, and randomization
- **Amplitude Control**: ADSR envelope and independent ramping system
- **Filter Section**: Resonant lowpass filter with envelope and ramping
- **Feedback System**: Multiple feedback routing options with variable depth
- **Delay Effects**: Multi-tap stereo delay with independent parameters

### 2.2 Particle Structure

A "particle" consists of 15 identical oscillators arranged in a binary tree:

- 7 Operators (OP1-OP7): Function primarily as modulators
- 8 Carriers (CAR1-CAR8): Generate the final audio output

```


                       ┌──────────┐
                       │   OP1    │
                       └─────┬────┘
                   ┌─────────┴─────────────────────────────┐
             ┌─────▼─────┐                           ┌─────▼─────┐
             │    OP2    │                           │    OP3    │
             └──────┬────┘                           └─────┬─────┘
        ┌───────────┴────────┐                     ┌───────┴───────────┐
  ┌─────▼─────┐        ┌─────▼─────┐       ┌───────▼─────┐       ┌─────▼─────┐
  │    OP4    │        │    OP5    │       │     OP6     │       │    OP7    │
  └──────┬────┘        └─────┬─────┘       └──────┬──────┘       └─────┬─────┘
 ┌───────┴────┐      ┌───────┴────┐      ┌────────┴────────┐   ┌───────┴────────┐
┌─▼──┐      ┌─▼──┐  ┌─▼──┐      ┌─▼──┐  ┌─▼──┐          ┌─▼──┐ ┌─▼──┐         ┌─▼──┐
│CAR1│      │CAR2│  │CAR3│      │CAR4│  │CAR5│          │CAR6│ │CAR7│         │CAR8│
└─┬┬─┘      └─┬┬─┘  └─┬┬─┘      └─┬┬─┘  └─┬┬─┘          └─┬┬─┘ └─┬┬─┘         └─┬┬─┘
  ││          ││      ││          ││      ││              ││     ││             ││
┌─▼▼─┐      ┌─▼▼─┐  ┌─▼▼─┐      ┌─▼▼─┐  ┌─▼▼─┐          ┌─▼▼─┐ ┌─▼▼─┐         ┌─▼▼─┐
│OUT │      │OUT │  │OUT │      │OUT │  │OUT │          │OUT │ │OUT │         │OUT │
│1/2 │      │3/4 │  │5/6 │      │7/8 │  │9/10│          │11/12│ │13/14│       │15/16│
└────┘      └────┘  └────┘      └────┘  └────┘          └────┘ └────┘         └────┘
```

## 3. Oscillator Parameters

Each oscillator contains identical parameter sets across these categories:

### 3.1 Oscillator Bank Parameters

- **Wave Type**: Selection from built-in wavetable library
- **Number of Oscillators**: 1-20 oscillators per voice
- **Detune Amount**: Frequency spread between oscillators
- **Detune Mode**: Linear, Exponential, or Random distribution
- **Spread**: Stereo width of oscillator bank
- **Phase Spread**: Phase distribution across oscillators
- **Amplitude Distribution**: Equal, Decreasing, Increasing, Triangle, or Bell

### 3.2 Frequency Control Parameters

- **Frequency Mode**: MIDI Note or Manual control
- **Manual Frequency**: Direct frequency control when in manual mode
- **Coarse Detune**: Semitone adjustment (-24 to +24)
- **Fine Detune**: Cent adjustment (-100 to +100)
- **Slew Delay**: Time before frequency transition begins
- **Slew Time**: Duration of frequency transition
- **Start Randomization**: Random variation of starting frequency
- **Start Slew**: Frequency offset at start of note
- **End Slew**: Frequency offset at end of transition
- **Frequency Envelope Depth**: Intensity of frequency envelope

### 3.3 Envelope Parameters

- **Frequency ADSR**: Attack, Decay, Sustain, and Release for frequency
- **Amplitude ADSR**: Attack, Decay, Sustain, and Release for amplitude

### 3.4 Ramp Parameters

- **Amplitude Ramp Delay**: Time before amplitude ramp begins
- **Amplitude Ramp Time**: Duration of amplitude transition
- **Amplitude Ramp Start**: Initial amplitude value
- **Amplitude Ramp End**: Final amplitude value

### 3.5 Filter Parameters

- **Filter Resonance**: Resonance amount for lowpass filter
- **Filter Ramp Delay**: Time before filter sweep begins
- **Filter Ramp Time**: Duration of filter transition
- **Filter Ramp Start**: Initial filter cutoff frequency
- **Filter Ramp End**: Final filter cutoff frequency

### 3.6 Feedback Parameters

- **Feedback Source**: Off, Pre-Delay, or Post-Delay
- **Feedback Depth**: Amount of signal fed back into oscillator

### 3.7 Delay Parameters

- **Left Tap Times**: Three delay times for left channel
- **Right Tap Times**: Three delay times for right channel
- **Left Feedback**: Amount of feedback in left delay line
- **Right Feedback**: Amount of feedback in right delay line

## 4. Modulation Architecture

### 4.1 Modulation Process

The FM synthesis works through these steps:

1. Each oscillator generates its own signal using its oscillator bank
2. The signal passes through the oscillator's complete processing chain
3. Operators send their processed output to modulate the frequency of destination oscillators
4. Carriers output their processed audio to assigned channel pairs

### 4.2 Modulation Routing

The default binary tree routing follows this structure:

- OP1 modulates OP2 and OP3
- OP2 modulates OP4 and OP5
- OP3 modulates OP6 and OP7
- OP4 modulates CAR1 and CAR2
- OP5 modulates CAR3 and CAR4
- OP6 modulates CAR5 and CAR6
- OP7 modulates CAR7 and CAR8

### 4.3 Signal Flow (Per Oscillator)

```
Copy

Oscillator Bank → Frequency Processing → Amplitude Processing → 
Filter → Feedback → Delay → Output/Modulation
```

## 5. Particle Implementation

### 5.1 Particle Parameters

A particle contains:

- 7 operators with full parameter sets
- 8 carriers with full parameter sets
- Global particle parameters (master volume, global effects)

### 5.2 Inter-oscillator Communication

- Operators calculate their output based on their parameter settings
- This output is used to modulate the frequency of downstream oscillators
- Modulation occurs at the frequency processing stage
- Each oscillator remains fully independent in all other aspects

## 6. Multi-Particle System

### 6.1 Particle Organization

Multiple particles can coexist, each with:

- Complete set of 15 oscillators
- Independent parameter sets
- Dedicated MIDI control channel (MPE, Polyphonic, or Unison--default)

### 6.2 Resource Allocation

- Particles share the wavetable library for efficiency
- Processing occurs independently for each particle
- Output mixing combines all particle outputs

## 7. Implementation Approach

### 7.1 Development Phases

#### Phase 1: Single Oscillator Refinement

- Ensure all oscillator features work correctly
- Optimize performance for multi-oscillator banks
- Create comprehensive parameter management system

#### Phase 2: Single Branch Implementation

- Implement OP1 → OP2 → OP4 → (CAR1, CAR2) chain
- Verify modulation behavior
- Test all oscillator parameters

#### Phase 3: Complete Particle

- Add remaining oscillators
- Implement full routing structure
- Test complex modulation paths

#### Phase 4: Multi-Particle Support

- Enable multiple particles
- Create inter-particle routing options
- Implement resource sharing

### 7.2 Performance Considerations

- Selective activation of oscillators based on modulation depth
- Dynamic allocation of oscillator banks based on usage
- Parallel processing of particles when possible
- Optimization of critical DSP functions

## 8. User Interface

### 8.1 Main Interface Elements

- **Particle Selector**: Switch between active particles
- **Oscillator Navigator**: Visual representation of modulation tree
- **Parameter Panels**: Controls for the selected oscillator
- **Global Controls**: Master parameters and routing options
- **Preset Manager**: Save and recall particle configurations

### 8.2 Parameter Organization

- **Hierarchical Naming**: particle1.op1.wave_type, particle1.car1.filter.cutoff, etc.
- **Tabbed Interface**: Separate tabs for different parameter categories
- **Visualization Tools**: Modulation flow diagrams and activity monitors
- **Macro Controls**: Parameters that affect multiple oscillators simultaneously

## 9. Preset System

### 9.1 Preset Storage

- YAML-based format for human readability
- Hierarchical structure matching the parameter organization
- Versioning to handle future enhancements

### 9.2 Preset Categories

- Factory presets demonstrating different synthesis techniques
- User presets with extended metadata
- Partial presets for specific oscillators or parameter groups

## 10. Future Extensions

### 10.1 Advanced Features

- Cross-branch modulation options
- Additional oscillator types and filter models
- Expanded feedback routing options
- Enhanced spatial audio capabilities

### 10.2 Integration

- MIDI learn functionality for hardware controllers
- OSC support for network control
- Export capabilities for rendered audio

## 11. Technical Requirements

- Python 3.7+
- Pyo audio library for DSP
- PyQt5 for user interface
- Multiprocessing support for parallel processing
- Hardware with multi-core CPU for optimal performance

## 12. Conclusion

Caelux Mini represents an innovative approach to FM synthesis by treating each oscillator in the modulation chain as a complete synthesis unit. This design provides unprecedented flexibility for sound design while maintaining a coherent structure through the particle concept. The implementation strategy focuses on incremental development, ensuring each component works correctly before adding complexity.