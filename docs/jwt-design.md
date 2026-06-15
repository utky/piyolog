# JWT 仕様と Haskell 実装戦略 設計書

> **関連ドキュメント**: `docs/gcs-api-design.md`（GCS API の認証フロー全体はそちらを参照）

---

## 1. JWT とは何か（仕様概要）

### RFC 7519

JWT (JSON Web Token) は RFC 7519 で定義されたトークン形式で、
当事者間でクレーム（主張・属性）を JSON として安全に伝達するための仕様。
JWS (JSON Web Signature, RFC 7515) または JWE (JSON Web Encryption) によって保護される。

### 3つのパートと構造

JWT はドット (`.`) で区切られた3つの Base64URL エンコード文字列で構成される。

```
<Base64URL(Header)>.<Base64URL(Payload)>.<Base64URL(Signature)>
```

**例（RS256 署名済みトークン）:**

```
eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9
.eyJpc3MiOiJzYUBwcm9qZWN0LmlhbS5nc2VydmljZWFjY291bnQuY29tIiwiZXhwIjoxNjk5OTk5OTk5fQ
.（署名バイト列を Base64URL エンコードしたもの）
```

### Base64URL エンコードとは

通常の Base64 から以下の変換を行った形式:

| Base64 文字 | Base64URL 文字 | 理由 |
|------------|---------------|------|
| `+` | `-` | URL の区切り文字と衝突しない |
| `/` | `_` | URL のパス区切りと衝突しない |
| `=` (パディング) | 省略 | URL クエリパラメータでの問題を回避 |

### 署名アルゴリズムの種類

| アルゴリズム | 種別 | 鍵 | 主な用途 |
|------------|------|-----|---------|
| HS256 | HMAC-SHA256 | 共通鍵 | 同一サービス内の検証 |
| RS256 | RSA-SHA256 | 公開鍵/秘密鍵ペア | サーバー間認証（Google OAuth2 等） |
| ES256 | ECDSA-SHA256 | 公開鍵/秘密鍵ペア | モバイル・IoT（鍵が小さい） |

**HS256 と RS256 の違い:**

- **HS256**: 署名と検証に同じ共通鍵を使う。鍵を共有した相手しか検証できない
- **RS256**: 秘密鍵で署名し、対応する公開鍵で検証。署名者だけが鍵を持てばよく、検証者には公開鍵を配布するだけでよい

Google OAuth2 サービスアカウント認証では **RS256** を使用する。

---

## 2. JWT の構造詳解

### Header（ヘッダー）

アルゴリズムとトークンタイプを宣言する JSON オブジェクト。

```json
{
  "alg": "RS256",
  "typ": "JWT"
}
```

| フィールド | 意味 | 値（Google OAuth2 の場合） |
|-----------|------|--------------------------|
| `alg` | 署名アルゴリズム | `"RS256"` |
| `typ` | トークンタイプ | `"JWT"` |

### Payload（ペイロード / クレームセット）

クレーム（主張）の集合を表す JSON オブジェクト。

#### 標準クレーム（RFC 7519 で定義）

| クレーム | 名称 | 型 | 説明 |
|---------|------|----|------|
| `iss` | Issuer | StringOrURI | トークンの発行者 |
| `sub` | Subject | StringOrURI | トークンの主体（ユーザー等） |
| `aud` | Audience | StringOrURI または配列 | トークンの受信対象 |
| `iat` | Issued At | NumericDate（UNIX秒） | 発行時刻 |
| `exp` | Expiration Time | NumericDate（UNIX秒） | 有効期限 |
| `nbf` | Not Before | NumericDate（UNIX秒） | この時刻以前は無効 |
| `jti` | JWT ID | String | トークンの一意識別子 |

#### Google OAuth2 固有のクレーム

Google が要求するクレームには標準にない `scope` が含まれる（詳細はセクション4を参照）。

**例（GCS アクセス用）:**

```json
{
  "iss": "sa@project.iam.gserviceaccount.com",
  "scope": "https://www.googleapis.com/auth/devstorage.read_write",
  "aud": "https://oauth2.googleapis.com/token",
  "iat": 1700000000,
  "exp": 1700003600
}
```

### Signature（署名）

Header と Payload を秘密鍵で署名したもの。

```
Signature = RS256(
  base64url(Header) + "." + base64url(Payload),
  privateKey
)
```

署名はバイト列として生成され、最終的に Base64URL エンコードされてトークンの第3パートになる。

---

## 3. RS256 署名の仕組み

### 公開鍵暗号（RSA）の基本

RSA は非対称暗号方式。互いに対応する鍵ペア（秘密鍵と公開鍵）を使う。

- **秘密鍵**: 持ち主だけが保持。署名の生成に使う
- **公開鍵**: 広く配布してよい。署名の検証に使う

「秘密鍵で署名 → 誰でも公開鍵で検証できる」という性質が、サーバー間の身元証明に適している。

### RS256 = RSA + SHA-256

RS256 は `RSASSA-PKCS1-v1_5` という RSA 署名スキームで、
ハッシュ関数として SHA-256 を使う。

### 署名の生成手順

```
1. base64url(Header) を計算
2. base64url(Payload) を計算
3. signing_input = base64url(Header) + "." + base64url(Payload)  （ASCII文字列）
4. digest = SHA-256(signing_input)
5. signature_bytes = RSA-PKCS1v15-Sign(digest, privateKey)
6. 署名済み JWT = signing_input + "." + base64url(signature_bytes)
```

### 検証フロー（受信側）

```
受信した JWT を Header / Payload / Signature に分割
    ↓
Signature を base64url デコードして signature_bytes を得る
    ↓
signing_input = Header + "." + Payload （元のエンコード文字列）
    ↓
RSA-PKCS1v15-Verify(SHA-256(signing_input), signature_bytes, publicKey)
    ↓
検証成功 → Payload の内容（クレーム）を信頼できる
```

Google の場合、Google 側の公開鍵（`https://www.googleapis.com/oauth2/v3/certs`）で JWT を検証する。

---

## 4. Google OAuth2 サービスアカウント認証での JWT 利用

### なぜ JWT が必要か

Google OAuth2 には複数のフロー（認可コードフロー、インプリシットフロー等）があるが、
**サービスアカウント（サーバー間認証）** では JWT Bearer フローを使う。

ユーザーが関与しないサーバー間通信では:

- ブラウザリダイレクトが不可能
- リフレッシュトークンは不要（アカウントはサービスアカウントなのでインタラクティブなログインがない）
- サービスアカウントの秘密鍵で自分自身の権限を証明する

そのため、**「自分が誰であるかを示す JWT を秘密鍵で自ら署名し、それをアクセストークンと交換する」**フローになる。

### Google が要求するクレーム

| クレーム | 必須 | 値 |
|---------|------|-----|
| `iss` | 必須 | サービスアカウントのメールアドレス（`client_email`）|
| `scope` | 必須 | 要求するスコープ（スペース区切り複数指定可） |
| `aud` | 必須 | `"https://oauth2.googleapis.com/token"` 固定 |
| `iat` | 必須 | 現在の UNIX タイムスタンプ（秒） |
| `exp` | 必須 | `iat + 3600` 以内（最大1時間） |
| `sub` | 任意 | ドメイン全体の委任（Domain-Wide Delegation）を使う場合のみ |

### アクセストークン取得フロー

```
[サービスアカウント JSON キーファイル]
    │
    ├── client_email → JWT の iss クレーム
    └── private_key  → RS256 署名に使用
          │
          ↓
[JWT 生成（Header + Payload + RS256署名）]
          │
          ↓
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=<署名済みJWT>
          │
          ↓
[レスポンス]
{
  "access_token": "ya29.xxx",
  "expires_in": 3600,
  "token_type": "Bearer"
}
          │
          ↓
Authorization: Bearer ya29.xxx を付与して GCS API を呼び出す
```

### トークンのライフサイクルとキャッシュ戦略

- アクセストークンの有効期間: **1時間（3600秒）**
- リフレッシュトークンは発行されない
- 期限切れ後は JWT を再生成してトークンを再取得する

**推奨キャッシュ戦略（Haskell での実装例）:**

```haskell
data TokenCache = TokenCache
  { cachedToken   :: Text
  , tokenExpiresAt :: UTCTime
  }

-- 有効期限の少し前（例: 5分前）に再取得する
isTokenValid :: TokenCache -> UTCTime -> Bool
isTokenValid cache now =
  addUTCTime (-300) (tokenExpiresAt cache) > now
```

`IORef TokenCache` または `MVar TokenCache` でスレッドセーフに管理し、
リクエスト毎に有効性チェックを行う設計が実用的。

---

## 5. Haskell 実装戦略（jose ライブラリ）

### jose パッケージの構造

`jose` パッケージ（Hackage）は JWS (RFC 7515) / JWE (RFC 7516) / JWK (RFC 7517) / JWA (RFC 7518) / JWT (RFC 7519) を実装したライブラリ。

主に使用するモジュール:

| モジュール | 役割 |
|-----------|------|
| `Crypto.JWT` | `ClaimsSet` の構築・`signClaims` による署名 |
| `Crypto.JOSE.JWK` | JWK（JSON Web Key）形式での鍵管理 |
| `Crypto.JOSE.Compact` | コンパクトシリアライズ（`encodeCompact`） |
| `Crypto.JOSE.Error` | エラー型 |

### PEM 形式の RSA 秘密鍵を JWK としてロードする

サービスアカウント JSON の `private_key` フィールドは PEM 形式の文字列。
`jose` はこれを直接 JWK に変換できる。

```haskell
import Crypto.JOSE.JWK (JWK, fromRSA)
import Crypto.PubKey.RSA (PrivateKey)
import Data.PEM (pemParseBS, pemContent)
import Data.X509 (decodeSignedObject, PrivKeyRSA(..))
import qualified Data.ByteString as BS

-- PEM 文字列（\n エスケープあり）から JWK をロードする
loadJWKFromPem :: BS.ByteString -> Either String JWK
loadJWKFromPem pemBytes = do
  pems <- pemParseBS pemBytes
  pem  <- case pems of
            (p:_) -> Right p
            []    -> Left "No PEM block found"
  -- DER デコード → RSA 秘密鍵 → JWK 変換
  ...
```

> **実用的なアプローチ**: `jose` の `Crypto.JOSE.JWK` は `Data.X509` と組み合わせて使う。
> サービスアカウント JSON の `private_key` は PKCS#8 形式 (`BEGIN PRIVATE KEY`) であることが多い。

### ClaimsSet の組み立て

`ClaimsSet` は `lens` を使ったビルダーパターンで組み立てる。

```haskell
import Crypto.JWT
import Control.Lens ((&), (?~))
import Data.Time (getCurrentTime, addUTCTime)
import qualified Data.Text as T

buildGcsClaims :: T.Text   -- client_email
               -> T.Text   -- scope URI
               -> IO ClaimsSet
buildGcsClaims email scope = do
  now <- getCurrentTime
  let expiry = addUTCTime 3600 now
  return $ emptyClaimsSet
    & claimIss ?~ fromString (T.unpack email)
    & claimAud ?~ Audience [fromString "https://oauth2.googleapis.com/token"]
    & claimIat ?~ NumericDate now
    & claimExp ?~ NumericDate expiry
    & addClaim "scope" (String scope)
```

`addClaim` で標準外のクレーム（`scope`）を追加できる。

### signClaims による署名

`signClaims` は `JOSE` モナド（内部的には `ExceptT JWTError` ベース）で動作する。

```haskell
import Crypto.JWT
import Crypto.JOSE.JWS (newJWSHeader)

signGcsJWT :: JWK -> ClaimsSet -> IO (Either JWTError SignedJWT)
signGcsJWT jwk claims = runJOSE $ do
  alg <- bestJWSAlg jwk   -- RSA 鍵なら RS256 が自動選択される
  signClaims jwk (newJWSHeader ((), alg)) claims
```

- `bestJWSAlg`: 鍵の種類から最適なアルゴリズムを推論（RSA → RS256）
- `newJWSHeader`: JWS ヘッダー（`alg` + `typ`）を構築
- `signClaims`: ヘッダーとクレームセットを署名して `SignedJWT` を返す

### コンパクトシリアライズ（encodeCompact）でテキスト化

```haskell
import Crypto.JOSE.Compact (encodeCompact)
import qualified Data.ByteString.Lazy as BL

-- SignedJWT をドット区切りの文字列に変換
serializeJWT :: SignedJWT -> BL.ByteString
serializeJWT = encodeCompact
```

`encodeCompact` は `header.payload.signature` 形式の `ByteString` を返す。
HTTP リクエストの `assertion` パラメータとしてそのまま使用できる。

### エラーハンドリング（JOSE モナド / runJOSE）

```haskell
import Crypto.JOSE (JOSE, runJOSE)
import Crypto.JOSE.Error (Error)

-- runJOSE は IO (Either Error a) を返す
example :: JWK -> ClaimsSet -> IO ()
example jwk claims = do
  result <- runJOSE @JWTError $ do
    alg <- bestJWSAlg jwk
    signClaims jwk (newJWSHeader ((), alg)) claims
  case result of
    Left err  -> putStrLn $ "JWT 署名エラー: " <> show err
    Right jwt -> putStrLn $ "JWT 生成成功"
```

`JWTError` は `AsJWTError` 型クラスで扱われ、署名失敗・鍵不一致・クレーム検証失敗等のエラーを表す。

---

## 6. 実装コード例（Haskell）

### 全体像

```
loadServiceAccountJson
    │
    ├── client_email: Text
    └── private_key:  ByteString (PEM)
          │
          ↓
loadJwkFromPem :: ByteString -> IO JWK
          │
          ↓
buildGcsClaims :: Text -> Text -> IO ClaimsSet
          │
          ↓
signGcsJwt :: JWK -> ClaimsSet -> IO (Either JWTError SignedJWT)
          │
          ↓
fetchAccessToken :: SignedJWT -> Manager -> IO Text
          │
          ↓
callGcsApi :: Text -> Manager -> IO Response
```

### 型定義

```haskell
module GCS.Auth where

import Crypto.JWT        (JWK, ClaimsSet, SignedJWT, JWTError)
import Data.Text         (Text)
import Network.HTTP.Client (Manager)

-- サービスアカウント情報
data ServiceAccount = ServiceAccount
  { saEmail      :: Text
  , saPrivateKey :: JWK
  }

-- アクセストークン（有効期限付き）
data AccessToken = AccessToken
  { atToken     :: Text
  , atExpiresAt :: UTCTime
  }
```

### JWT 生成〜アクセストークン取得

```haskell
{-# LANGUAGE OverloadedStrings #-}

module GCS.Auth where

import Control.Lens          ((&), (?~))
import Crypto.JWT
import Crypto.JOSE.Compact   (encodeCompact)
import Data.Aeson            (decode, (.:))
import Data.String           (fromString)
import Data.Time             (getCurrentTime, addUTCTime)
import Network.HTTP.Client
import Network.HTTP.Client.TLS (newTlsManager)
import qualified Data.ByteString.Lazy as BL
import qualified Data.Text            as T
import qualified Data.Text.Encoding   as TE

-- | JWT クレームセットを構築する
buildClaims :: T.Text   -- ^ client_email
            -> T.Text   -- ^ scope
            -> IO ClaimsSet
buildClaims email scope = do
  now <- getCurrentTime
  return $ emptyClaimsSet
    & claimIss ?~ fromString (T.unpack email)
    & claimAud ?~ Audience [fromString "https://oauth2.googleapis.com/token"]
    & claimIat ?~ NumericDate now
    & claimExp ?~ NumericDate (addUTCTime 3600 now)
    & addClaim "scope" (String scope)

-- | JWK で ClaimsSet に RS256 署名する
signJwt :: JWK -> ClaimsSet -> IO (Either JWTError SignedJWT)
signJwt jwk claims = runJOSE $ do
  alg <- bestJWSAlg jwk
  signClaims jwk (newJWSHeader ((), alg)) claims

-- | OAuth2 トークンエンドポイントにアクセストークンを要求する
fetchAccessToken :: SignedJWT -> Manager -> IO (Either String T.Text)
fetchAccessToken jwt manager = do
  let jwtBytes  = BL.toStrict (encodeCompact jwt)
      body      = "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer"
               <> "&assertion=" <> jwtBytes
  initReq <- parseRequest "POST https://oauth2.googleapis.com/token"
  let req = initReq
        { requestHeaders = [("Content-Type", "application/x-www-form-urlencoded")]
        , requestBody    = RequestBodyBS body
        }
  response <- httpLbs req manager
  case decode (responseBody response) of
    Nothing   -> return (Left "レスポンスの JSON パース失敗")
    Just obj  -> case obj .: "access_token" of
      Just token -> return (Right token)
      Nothing    -> return (Left "access_token フィールドが存在しない")

-- | エントリポイント: サービスアカウント情報からアクセストークンを取得する
getGcsAccessToken :: ServiceAccount -> Manager -> IO (Either String T.Text)
getGcsAccessToken sa manager = do
  claims <- buildClaims (saEmail sa) "https://www.googleapis.com/auth/devstorage.read_write"
  result <- signJwt (saPrivateKey sa) claims
  case result of
    Left err  -> return (Left (show err))
    Right jwt -> fetchAccessToken jwt manager
```

### GCS API 呼び出し（Bearer トークン付与）

```haskell
-- | アクセストークンを Bearer として GCS API を呼び出す
callGcsApi :: T.Text     -- ^ アクセストークン
           -> String     -- ^ URL
           -> Manager
           -> IO BL.ByteString
callGcsApi token url manager = do
  req <- parseRequest url
  let req' = req
        { requestHeaders =
            [ ("Authorization", "Bearer " <> TE.encodeUtf8 token)
            , ("Accept", "application/json")
            ]
        }
  responseBody <$> httpLbs req' manager
```

---

## 7. 参考リンク

### RFC 仕様

| RFC | タイトル | URL |
|-----|---------|-----|
| RFC 7519 | JWT (JSON Web Token) | https://datatracker.ietf.org/doc/html/rfc7519 |
| RFC 7515 | JWS (JSON Web Signature) | https://datatracker.ietf.org/doc/html/rfc7515 |
| RFC 7517 | JWK (JSON Web Key) | https://datatracker.ietf.org/doc/html/rfc7517 |
| RFC 7518 | JWA (JSON Web Algorithms) | https://datatracker.ietf.org/doc/html/rfc7518 |

### Hackage（Haskell パッケージ）

| パッケージ | URL |
|-----------|-----|
| jose | https://hackage.haskell.org/package/jose |
| jose: Crypto.JWT | https://hackage.haskell.org/package/jose/docs/Crypto-JWT.html |

### Google 公式ドキュメント

| リソース | URL |
|---------|-----|
| OAuth2 サービスアカウント認証 | https://developers.google.com/identity/protocols/oauth2/service-account |
| JWT の使用（Google API） | https://developers.google.com/identity/protocols/oauth2/service-account#jwt-auth |
