/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

// Generate expanded color palette with ~500 colors
const generateColorPalette = () => {
    const colors = [];
    
    // Original AWS colors
    const awsColors = [
        {"name": "Berry", "hex": "#9e1f63"},
        {"name": "Aqua - Bright", "hex": "#a6e7ce"},
        {"name": "AWS Orange", "hex": "#ff6633"},
        {"name": "AWS Yellow", "hex": "#f3e502"},
        {"name": "Green Apple", "hex": "#18ab4b"},
        {"name": "Aqua", "hex": "#00464f"},
        {"name": "Sea Blue", "hex": "#005276"},
        {"name": "Paper", "hex": "#f1f3f3"},
        {"name": "Plum - Medium", "hex": "#504bab"},
        {"name": "Plum - Bright", "hex": "#7e93ee"},
        {"name": "Berry - Medium", "hex": "#c9208a"},
        {"name": "Sea Blue - Bright", "hex": "#7cd1ea"},
        {"name": "Berry - Bright", "hex": "#ff99ff"},
        {"name": "Smile", "hex": "#ff9900"},
        {"name": "Green Apple - Medium", "hex": "#ade422"},
        {"name": "Green Apple - Bright", "hex": "#e4fdbf"},
        {"name": "Aqua - Medium", "hex": "#36c2b4"},
        {"name": "Plum", "hex": "#262262"},
        {"name": "Sea Blue - Medium", "hex": "#008296"},
        {"name": "Squid Ink", "hex": "#232F3E"},
        {"name": "Stone", "hex": "#d4dada"}
    ];
    
    
    
    // Generate systematic color variations
    for (let h = 0; h < 360; h += 15) { // 24 hues
        for (let s = 20; s <= 100; s += 20) { // 5 saturations
            for (let l = 20; l <= 80; l += 20) { // 4 lightness levels
                const hex = hslToHex(h, s, l);
                colors.push({
                    name: `HSL(${h},${s}%,${l}%)`,
                    hex: hex
                });
            }
        }
    }

    colors.push(...awsColors);
    
    return colors;
};

// Convert HSL to HEX
const hslToHex = (h, s, l) => {
    l /= 100;
    const a = s * Math.min(l, 1 - l) / 100;
    const f = n => {
        const k = (n + h / 30) % 12;
        const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
        return Math.round(255 * color).toString(16).padStart(2, '0');
    };
    return `#${f(0)}${f(8)}${f(4)}`;
};

export const AWS_COLOR_PALETTE = generateColorPalette();
