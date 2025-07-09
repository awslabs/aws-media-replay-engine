export const setGeneralLoading = (loading: boolean) => {
  localStorage.setItem('generalLoading', JSON.stringify(loading));
};

export const getGeneralLoading: () => boolean = () => {
  const loading = localStorage.getItem('generalLoading');
  return JSON.parse(loading ? loading : 'true');
};

export const requestTracker = {
  requestList: [] as string[],
  addRequest(requestID: string): void {
    this.requestList.push(requestID);
  },
  removeRequest(requestID: string): void {
    this.requestList = this.requestList.filter((id) => id !== requestID);
  },
};
