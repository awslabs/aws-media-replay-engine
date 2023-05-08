# DetectAudioPeaks #

**MRE Plugin Class**
- Featurer

**Description**:

"This plugin attempts to detect where peaks in audio are occuring in an audio track by calculating the rolling average and standard deviation of audio amplitudes"

**Applies to Media Type**:
- Video
- Audio (In Development)

**Use Cases**:
- Use crowd/announcer cheers/shouts/excitement to identify key moments 

**Dependencies**:
- MRE Helper libraries  
- ffmpeg
- numpy
- scipy

**ML Model dependencies**:
- None

**Other plugin dependencies**:
- None

**Parameter inputs**:
- TrackNumber >> Audio track from video that is being used for calculations.
- bin_size_seconds >> Subset size used to calculate the rolling average of the audio amplitude.
- look_back_bin_cnt >> Used to calculate the amplitude rolling average as a convolution of two one dimensional sequences.
- num_stddevs_filter >> How many standard deviations away from the rolling mean amplitude does an audio peak's amplitude have to be to be considered significant.
- filter_lowcut >>  Low critical frequency for Butterworth digital and analog filter.
- filter_highcut >> High critical frequency for Butterworth digital and analog filter.
 
**Output attributes**:
- Label >> Name of the feature to be detected in this plugin.

**IAM permissions (least privilege)**:
- None
