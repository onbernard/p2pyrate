# Ensure that a command is passed as an argument
if [ $# -lt 1 ]; then
  echo "Usage: $0 <command>"
  exit 1
fi

# Create a unique filename for the pcap file
PCAP_FILE="capture_$(date +%Y%m%d_%H%M%S).pcap"

# Function to stop tcpdump on Ctrl+C or when the command finishes
cleanup() {
  echo "Stopping tcpdump and saving to $PCAP_FILE..."
  sudo kill $TCPDUMP_PID
  wait $TCPDUMP_PID 2>/dev/null
  exit 0
}

# Trap Ctrl+C (SIGINT) to call the cleanup function
trap cleanup SIGINT

# Start tcpdump and write output to a pcap file
echo "Starting tcpdump and capturing network traffic to $PCAP_FILE..."
sudo tcpdump -w $PCAP_FILE &
TCPDUMP_PID=$!

# Run the command passed as argument
# echo "Running command: $@"
# "$@"
echo "Running command"
aria2c $@
cleanup
