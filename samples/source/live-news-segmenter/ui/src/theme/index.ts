import { Theme } from '@aws-amplify/ui-react';

export const AWS_ORANGE = '#FF9901';
export const AWS_DARK = '#232F3E';
export const AWS_DARKER = '#16191F';
export const AWS_DARK_GREY = '#4F5965';
export const AWS_LIGHT_GREY = '#D5DBDB';
export const WHITE = '#ffffff';
export const BLACK = '#000000';
export const AWS_BORDER_COLOR = '#545B64';
export const AWS_CLOSE_ICON_COLOR = '#879596';

export const theme: Theme = {
    name: 'nab-ui-theme',
    tokens: {
        colors: {
            font: {
                primary: {
                    value: WHITE,
                }
            },
        },
        components: {
            authenticator: {
                router: {
                    backgroundColor: AWS_DARK
                }
            },
            tabs: {
                item: {
                    color: WHITE,
                    _hover: {
                        color: AWS_ORANGE,
                    },
                    _active: {
                        color: AWS_ORANGE,
                        borderColor: AWS_ORANGE,
                    }
                }
            },
            fieldcontrol: {
                _focus: {
                    borderColor: AWS_ORANGE,
                    boxShadow: `0px 0px 0px 2px ${AWS_ORANGE}`,
                },
            },
            button: {
                color: WHITE,
                _active: {
                    backgroundColor: AWS_ORANGE,
                    borderColor: AWS_ORANGE,
                },
                _focus: {
                    backgroundColor: AWS_ORANGE,
                    borderColor: AWS_ORANGE,
                },
                _hover: {
                    color: AWS_ORANGE,
                },
                primary: {
                    backgroundColor: AWS_ORANGE,
                    color: AWS_DARK,
                    _hover: {
                        backgroundColor: AWS_DARK_GREY,
                        color: AWS_LIGHT_GREY
                    },
                    _focus: {
                        backgroundColor: AWS_ORANGE,
                    },
                    _active: {
                        backgroundColor: AWS_ORANGE,
                    },
                    _disabled: {
                        backgroundColor: AWS_DARK_GREY,
                        color: AWS_LIGHT_GREY
                    }
                },
                link: {
                    color: AWS_ORANGE,
                    _hover: {
                        color: AWS_DARK,
                    }
                }
            },
            field: {
                label: {
                    color: WHITE,
                }
            },
            placeholder: {
                startColor: AWS_DARK_GREY,
                endColor: "#585e66",
                borderRadius: "0"
            },
            table: {
                header: {
                    borderColor: AWS_BORDER_COLOR,
                },
                data: {
                    borderColor: AWS_BORDER_COLOR,
                },
                row: {
                    hover: {
                        backgroundColor: AWS_DARK,
                    }
                }
            },
            card: {
                outlined: {
                    backgroundColor: AWS_DARKER,
                    borderColor: AWS_BORDER_COLOR,
                }
            }
        },
    },
};