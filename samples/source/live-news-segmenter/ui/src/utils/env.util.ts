export const environments = {
    API_CONTENT_GROUP: import.meta.env.VITE_CONTROL_PLANE_ENDPOINT.replace(/\/$/, ""),
    API_EVENT: import.meta.env.VITE_CONTROL_PLANE_ENDPOINT.replace(/\/$/, ""),
    API_PROFILE: import.meta.env.VITE_CONTROL_PLANE_ENDPOINT.replace(/\/$/, ""),
    API_THEME: import.meta.env.VITE_CONTROL_PLANE_ENDPOINT + 'customapi',
    API_DATAPLANE: import.meta.env.VITE_API_DATAPLANE.replace(/\/$/, ""),
    API_STREAMING: import.meta.env.VITE_API_STREAMING,
    APP_REGION: import.meta.env.VITE_APP_REGION,
    APP_USER_POOL_ID: import.meta.env.VITE_APP_USER_POOL_ID,
    APP_CLIENT_ID: import.meta.env.VITE_APP_CLIENT_ID,
    APP_IDENTITY_POOL_ID: import.meta.env.VITE_APP_IDENTITY_POOL_ID,
}
