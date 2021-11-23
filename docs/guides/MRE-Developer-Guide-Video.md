![mre-header](mre-header-1.png)

# Developers Guide - Video Source Integration

MRE acts on video chunks in Amazon S3. There are many ways to accomplish this and the easiest is to use AWS Elemental Media Live. The Media Live service can work with live and VOD sources that get configured as channels. The alternative is to generate chunks using an independent method and push them to the designated S3 bucket. In either case, chunk size (in seconds) needs to be considered for the application. smaller chunk sizes will produce lower latency, but may increase the number of chunks needed to complete a segment (clip). MRE will help track the context of a segment across multiple sequential chunks that is used in the segmenter class plugin. This is done through the MRE helper library (AWS Lambda Layer).

The general guidance is to look at the average length of a segment (clip) and choose a chunk size that is approximately the same length.

When using AWS Elemental Media Live, know that MRE needs permissions to:
- Add and reconfigure a MediaLive channel output to reflect the configuration needs of the event profile (chunk size)  
- MRE creates an additional channel output group to write HLS file chunks to S3 for a specified size per the event profile
- An IAM policy is provided that you should add to your channel IAM Role to allow Media Live to write to the new output S3 location
- MRE currently supports SINGLE_CHANNEL class pipeline channel configuration. Contact us if you have an interest in STANDARD class
