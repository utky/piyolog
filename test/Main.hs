module Main (main) where

import Test.Hspec
import qualified Text.Piyolog (someFunc)

main :: IO ()
main =
  hspec $ do
    describe "Text.Piyolog.someFunc" $ do
      it "returns 'Hello'" $ do
        Text.Piyolog.someFunc `shouldBe` "Hello"
