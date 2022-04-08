self.mre_media_output_bucket.bucket_name

event_bus = events.EventBus.from_event_bus_arn(this, "ImportedEventBus", "arn:aws:events:us-east-1:111111111:event-bus/my-event-bus")

layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer, 
                    self.timecode_layer
                ]



self.timecode_layer


self.mre_edlgen_events_rule.node.add_dependency(self.eb_event_bus)