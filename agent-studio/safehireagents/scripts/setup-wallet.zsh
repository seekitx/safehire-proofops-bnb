#!/bin/zsh
set -euo pipefail

script_dir=${0:A:h}
project_root=${script_dir:h}
env_file="$project_root/.studio/.env.local"
bag_package="@bnbagent/studio-cli@0.0.13"

mkdir -p "$project_root/.studio"
touch "$env_file"
chmod 600 "$env_file"

read -s "wallet_password?Enter a new testnet Agent wallet password (hidden): "
print
if [[ -z "$wallet_password" ]]; then
  print -u2 "Password cannot be empty. No file was changed."
  exit 1
fi

tmp_file=$(mktemp "$project_root/.studio/.env.local.tmp.XXXXXX")
chmod 600 "$tmp_file"
found=false
while IFS= read -r line || [[ -n "$line" ]]; do
  if [[ "$line" == WALLET_PASSWORD=* ]]; then
    print -r -- "WALLET_PASSWORD=$wallet_password" >> "$tmp_file"
    found=true
  else
    print -r -- "$line" >> "$tmp_file"
  fi
done < "$env_file"
if [[ "$found" == false ]]; then
  print -r -- "WALLET_PASSWORD=$wallet_password" >> "$tmp_file"
fi
mv "$tmp_file" "$env_file"
chmod 600 "$env_file"

export WALLET_PASSWORD="$wallet_password"
unset wallet_password

cd "$project_root"
npx --yes "$bag_package" wallet new
print "Agent wallet created. The password was not printed."
