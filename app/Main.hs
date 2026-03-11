module Main where

import qualified Text.Piyolog (someFunc)

main :: IO ()
main = do
  putStrLn Text.Piyolog.someFunc
