            # Handle process termination
            if stop_event.is_set():
                send_discord_message(config["server_status_webhook"], 
                                  "Tile is being restarted for mod update", server_id)
                logger.info("Stopping server process")
                print("Stopping server process")
                
                try:
                    if process.poll() is None:
                        kill_process = psutil.Process(process.pid)
                        for proc in kill_process.children(recursive=True):
                            proc.kill()
                        kill_process.kill()
                except psutil.NoSuchProcess:
                    logger.warning("Process already terminated")
                except Exception as e:
                    logger.error(f"Error killing process: {e}")
                
                break
            else:
                # Process crashed or exited unexpectedly
                send_discord_message(config["server_status_webhook"], 
                                  "Tile Crashed: Restarting", server_id)
                logger.info("Server process has exited. It will be checked for restart conditions.")
                print("Server process has exited. It will be checked for restart conditions.")
                
                global crash_total
                crash_total += 1
                
                # Check the error log for any issues
                if error_log:
                    error_log.close()
                try:
                    with open(error_log_path, "r") as f:
                        error_content = f.read()
                        if error_content:
                            logger.error(f"Process error output: {error_content}")
                            print(f"Process error output: {error_content}")
                except Exception as e:
                    logger.error(f"Failed to read error log: {e}")
                
                logger.info(f"Process created with PID: {process.pid}")
            except WindowsError as win_err:
                logger.error(f"Windows error creating process: {win_err}")
                print(f"Windows error creating process: {win_err}")
                if error_log and not error_log.closed:
                    error_log.close()
                time.sleep(5)
                continue
            except Exception as e:
                logger.error(f"Error creating process: {e}")
                print(f"Error creating process: {e}")
                
                # Log more detailed error information
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(f"Detailed error: {error_traceback}")
                
                if error_log and not error_log.closed:
                    error_log.close()
                time.sleep(5)
                continue
