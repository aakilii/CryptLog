export {};

declare global {
  interface Window {
    google: GoogleNamespace;
    gapi: {
      load: (api: string, callback: () => void) => void;
    };
  }

  interface GoogleNamespace {
    accounts: {
      oauth2: {
        initTokenClient: (config: GoogleOAuth2TokenClientConfig) => GoogleOAuth2TokenClient;
      };
    };
    picker: GooglePicker;
  }

  interface GoogleOAuth2TokenClientConfig {
    client_id: string;
    scope: string;
    callback: (response: GoogleOAuth2TokenResponse) => void;
    error_callback?: (error: unknown) => void;
  }

  interface GoogleOAuth2TokenClient {
    requestAccessToken: (options?: { prompt?: string }) => void;
  }

  interface GoogleOAuth2TokenResponse {
    access_token?: string;
    expires_in?: number;
    token_type?: string;
    scope?: string;
    error?: string;
    error_description?: string;
    error_uri?: string;
  }

  interface GooglePicker {
    DocsView: new (viewId: unknown) => GooglePickerDocsView;
    ViewId: {
      DOCS: unknown;
    };
    PickerBuilder: new () => GooglePickerBuilder;
    Action: {
      PICKED: string;
    };
    Response: {
      DOCUMENTS: string;
    };
  }

  interface GooglePickerDocsView {
    setMimeTypes: (mimeTypes: string) => GooglePickerDocsView;
  }

  interface GooglePickerBuilder {
    addView: (view: GooglePickerDocsView) => GooglePickerBuilder;
    setOAuthToken: (token: string) => GooglePickerBuilder;
    setDeveloperKey: (key: string) => GooglePickerBuilder;
    setCallback: (cb: (data: any) => void) => GooglePickerBuilder;
    build: () => GooglePickerInstance;
  }

  interface GooglePickerInstance {
    setVisible: (visible: boolean) => void;
  }
}


