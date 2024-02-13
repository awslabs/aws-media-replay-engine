/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {FormControl, FormLabel} from "@material-ui/core";
import DateTimePicker from 'react-datetime-picker'
import '../../../common/DateTimePicker.css';

const debounce = (func, timeout = 300) => {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => { func.apply(this, args); }, timeout);
  };
}

export const TimeFilter = (props) => {
    return (
        <FormControl>
            <FormLabel>{props.label}</FormLabel>
            <div>
                <DateTimePicker style={{}}
                    onChange={debounce((date) => {
                        console.log(date)
                        if (!date) {
                            props.onClearClick();
                        }
                        props.onChange(date);
                    })}
                    value={props.dateTime}
                    required
                    disableClock
                    disableCalendar
                    clearIcon={props.shouldHideIcon === true ? null : ""}
                    minDate={new Date(2000)}
                />
            </div>
        </FormControl>
    );
};