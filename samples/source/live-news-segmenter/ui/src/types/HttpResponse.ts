export interface HttpResponseSuccess<T> {
    success: true;
    data: T;
    LastEvaluatedKey?: string;
    StartFrom?: string;
}

export interface HttpResponseError {
    success: false;
    error: string;
}