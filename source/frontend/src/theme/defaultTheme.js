/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import {createMuiTheme} from '@material-ui/core/styles';

const defaultTheme = createMuiTheme({
    palette: {
        type: 'dark',
        background: {
            default: '#25272b'
        },
        primary: {
            main: '#fb5e03',
            contrastText: "#FFFFFF"
        },
        secondary: {
            main: '#17191e',
            contrastText: "#FFFFFF"
        },
        layout: {
            main: "#232F3E",
            contrastText: "#FFFFFF"
        },
        divider: '#C0C0C0'
    },
    typography: {
        fontFamily: 'AmazonEmber',
        htmlFontSize: 16,
        h1: {
            fontSize: '2em',
            fontFamily: 'AmazonEmberHeavy',
            fontWeight: 700
        },
        h2: {
            fontSize: '1.5em',
            fontFamily: 'AmazonEmberHeavy',
            fontWeight: 700
        },
        h3: {
            fontSize: '1.3em',
            fontFamily: 'AmazonEmberBold',
            fontWeight: 700
        },
        h4: {
            fontSize: '1.1em',
            fontFamily: 'AmazonEmberBold',
            fontWeight: 700
        },
        h6: {
            fontSize: '1.25em',
            fontFamily: 'AmazonEmberBold',
            fontWeight: 700
        },
        subtitle1: {
            fontSize: '1.25em',
            fontFamily: 'AmazonEmberMedium',
            fontWeight: 500
        },
        subtitle2: {
            fontSize: '1em',
            fontFamily: 'AmazonEmberMedium',
            fontWeight: 700
        },
        body1: {
            fontSize: '1em',
            fontFamily: 'AmazonEmberMedium'
        },
        body2: {
            fontSize: '1em',
        }
    }
});

defaultTheme.overrides = {
    MuiPaper: {
        root: {
            backgroundColor: defaultTheme.palette.secondary.main,
            padding: 20
        }
    },
    MuiCssBaseline: {
        '@global': {
            '*::-webkit-scrollbar': {
                width: '0.4em',
                maxHeight: 6,
            },
            '*::-webkit-scrollbar-thumb': {
                backgroundColor: defaultTheme.palette.secondary.contrastText,
            }
        }
    },
    MuiMenuItem: {
        root: {
            backgroundColor: defaultTheme.palette.secondary.main
        }
    },
    MuiSelect: {
        root: {
            backgroundColor: defaultTheme.palette.secondary.main,
        },
    },
    MuiMenu: {
        list: {
            padding: 0
        }
    },
    MuiTypography: {
        colorError: {
            paddingTop: '0.8vh',
            paddingLeft: '2vh'
        }
    },
    MuiTableRow: {
        head: {
            backgroundColor: "#1c2024"
        },
        root: {
            backgroundColor: defaultTheme.palette.secondary.main
        },
        hover: {
            cursor: "pointer"
        }
    },
    MuiTableCell: {
        stickyHeader: {
            backgroundColor: "#1c2024"
        },
        root: {
            padding: 10
        },
        head: {
            padding: 15
        },

    },
    MuiTablePagination: {
        root: {
            backgroundColor: "#1c2024"
        }
    },
    MuiLink: {
        root: {
            color: '#1976d2',
            fontSize: '1.1em',
        }
    },
    MuiFab: {
        sizeSmall: '0.5em'
    },
    MuiDivider: {
        light: {
            backgroundColor: '#626262'
        }
    },
    MuiButton: {
        root: {
            textTransform: 'None'
        }
    },
    MuiDialogTitle: {
        root: {
            backgroundColor: "#232F3E",
        }
    },
    MuiDialog: {
        paper: {
            padding: 0
        }
    }
};

export default defaultTheme;