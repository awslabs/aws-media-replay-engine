/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import {createMuiTheme} from '@material-ui/core/styles';


//@link https://cimdalli.github.io/mui-theme-generator/
//@todo set overrides for all core components,
// need to make sure imported components implement theming

const defaultTheme = createMuiTheme({
    palette: {
        primary: {
            main: "#025CFF",
            contrastText: "#ffffff"
        },
        secondary: {
            main: '#ffffff',
        },
        background: {
            default: '#2A313F',
        },
        divider: '#2A312B',
        text: {
            primary: '#ffffff'
        },
        layout: {
            main: '#000000',
            contrastText: '#ffffff'
        }
    },
    typography: {
        fontFamily: 'AmazonEmber',
        htmlFontSize: 16,
        h1: {
            fontSize: 60,
            fontFamily: 'AmazonEmberHeavy',
        },
        h2: {
            fontSize: 35,
            fontFamily: 'AmazonEmber',
        },
        h3: {
            fontSize: 25,
            fontFamily: 'AmazonEmber',
        },
        h4: {
            fontSize: 20,
            fontFamily: 'AmazonEmber',
        },
        h5: {
            fontFamily: 'AmazonEmberMedium',
        },
        h6: {
            fontSize: 25,
            fontFamily: 'AmazonEmberMedium',
        },
        subtitle1: {
            fontSize: 20,
            fontFamily: 'AmazonEmberMedium',
        }
    },
});

defaultTheme.overrides = {
    MuiCard: {
        root: {
            backgroundColor: '#2A313F'
        }
    },
    MuiButton: {
        outlined: {
            borderColor: defaultTheme.palette.secondary.main,
            borderRadius: 0.2
        },
    },
    MuiTextField: {
        root: {
            border: `1px solid white`,
            color: 'white',
            borderRadius: defaultTheme.shape.borderRadius,
            "&.disabled": {
                color: "white"
            }
        },
    }
};

export default defaultTheme;