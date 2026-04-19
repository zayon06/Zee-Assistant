import sys
import multiprocessing

if __name__ == "__main__":
    # Required to prevent infinite loop of spawns when running as an executable
    multiprocessing.freeze_support()
    
    # If launched with the internal server flag, act as the server
    if len(sys.argv) > 1 and sys.argv[1] == "--run-server":
        from server.main import main
        main()
    else:
        # Otherwise, act as the main client
        from client.main import main
        main()
