/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import SOCCER_IMAGE from '../assets/soccer_gradiant.svg';
import TENNIS_IMAGE from '../assets/tennis_gradiant.svg';
import GOLF_IMAGE from '../assets/golf_gradiant.svg';
import SWIMMING_IMAGE from '../assets/swimming_gradiant.svg';
import FOOTBALL_IMAGE from '../assets/football_gradiant.svg';
import SOCCER_DARK_IMAGE from '../assets/soccer.svg';
import TENNIS_DARK_IMAGE from '../assets/tennis.svg';
import GOLF_DARK_IMAGE from '../assets/golf.svg';
import SWIMMING_DARK_IMAGE from '../assets/swimming.svg';
import FOOTBALL_DARK_IMAGE from '../assets/football.svg';
import SOCCER_BACKGROUND_IMAGE from '../assets/soccer_background.jpg';
import TENNIS_BACKGROUND_IMAGE from '../assets/tennis_background.jpg';


export const CATEGORIES = [
    {
        title: "Tennis",
        image: TENNIS_IMAGE,
        hoverImage: TENNIS_DARK_IMAGE,
        backgroundImage: TENNIS_BACKGROUND_IMAGE
    },
    {
        title: "Soccer",
        image: SOCCER_IMAGE,
        hoverImage: SOCCER_DARK_IMAGE,
        backgroundImage: SOCCER_BACKGROUND_IMAGE
    },
    {
        title: "Golf",
        image: GOLF_IMAGE,
        hoverImage: GOLF_DARK_IMAGE
    },
    {
        title: "Swimming",
        image: SWIMMING_IMAGE,
        hoverImage: SWIMMING_DARK_IMAGE
    },
    {
        title: "Football",
        image: FOOTBALL_IMAGE,
        hoverImage: FOOTBALL_DARK_IMAGE
    }
];